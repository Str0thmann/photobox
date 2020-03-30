'''
    This is a PhotoBox Software

    @author Lars Stratmann
    @Version 2.0
    @modified: 29.09.2019

    What does the Program:
        This Software capture a Image with a camera over the USB port.
        After pressing the "start" button the Countdown starts and a preview Video stream starts.
        On the screen are the Countdown numbers transparent png images.
        If the Countdown is at 2 the preview Stream close an d the camera start focusing and capture the image.
        The captured Image will show on the Screen.
        If "abort" is pressed the Image will not be saved.
        If "recapture" is pressed the Image will be saved and the Countdown starts again.
        If "start" is pressed the Image will be saved and the preview video stream starts.

        After X time the screensaver starts and the preview Image or the preview video stream stops.

        Optional:
            The countdown can expand with an LED ring

    Functions:
        The Program is in 4 Threads splited, camera Control, ScreenSaver, LedControl and Countdown

        The Camera Thread start and stop the preview Viedo stream and start the Capturing.

        The ScreenSaver start after X Time inactive, and call a stop function in the Camera Thread

        The Countdown print transparent PNGs on the top Screen layer and call a start capturing function in the Camera Thread.

        The LedControl expands the the Countdown


    Hardware:
        Raspberry Pi 3+
        LCD Screen
        Nikon XXX
        Adafruit LED RGB Ring

    Requires:
        Remove for easy workflow, cause so the camera did not start automaticly
        bash sudo rm /usr/share/dbus-1/services/org.gtk.vfs.GPhoto2VolumeMonitor.service
        sudo rm /usr/share/gvfs/mounts/gphoto2.mount
        sudo rm usr/share/gvfs/remote-volume-monitors/gphoto2.mount
        sudo rm /usr/lib/gvfs/gvfs-gphoto2-volume-monitor
        sudo rm /usr/lib/gvfs/gvfsd-gphoto2



    Logging:
        Debug:
            - entering and leaving from Events
        INFO:
            - make a picture status
            -
        WARNING:
            - Could not connect to Server
            - could not make a picture -> reason
            - could not save the image, cause not enough space

        Critical:
            - no camera found
            - libarys not found


    TODO exception picture screen saver between each picture change, if nothing is found print no picture

    TODO please smile picture for the 2 seconds before taking the picture

    TODO LedControl

    TODO pngview check implement
'''

from threading import Thread, Event, Barrier
import time
import subprocess
import os
from sys import path
import sys
import signal
import glob
import atexit
import random
from PIL import Image
from gpiozero import Button
import board
import neopixel
import gphoto2 as gp
import logging
import io
import logging



# setup Logging
logging.basicConfig(filename=str(os.path.dirname(os.path.realpath(__file__))) + '/photobox.log', format='%(asctime)s %(levelname)s\tl:%(lineno)d %(threadName)s %(funcName)s: %(message)s', level=logging.DEBUG)


# boolean for Develop Modus
devModus = False

threads = {}
captured = False
imageDirectory = "/home/pi/Pictures/"
#imageDirectory = "/home/pi/server/"
imageFileType = "jpg"
lastCapturedImage = ""

noImageCapturedInfo = path[0] + "/" + "Files/keinFotofuerDich2.jpg"
noImageFound = path[0] + "/" + "Files/noImageFound.jpg"


saveOnServer = False
serverImageDirectory = "/home/pi/server/"


# The Time how long a picture will be show
diashowTime = 5

# FPS, can vary because of the performance
video_preview_fps = 20


captureButton = Button(27)
reCaptureButton = Button(17)
abortButton = Button(22)

# in seconds
screenSaverStartTimer = 120

capturedEvent = Event()


# Subprocess preview
videoPreviewEvent = Event()

preview_is_running = False

# Subprocess preview
videoPreviewSubProcess = False

# TODO correct implementation
# This is a Barrier for aktual 2 Parties, the Coutdown self and the LED Ring
# with a timeout from 2 sec
sync_Countdown_Barrier = Barrier(2, timeout=2)

# LED initial
ledCyclePin = board.D18
ORDER = neopixel.GRB


def exit_handler():
    print('My application is ending!')
    threads["Camera"].stop_all_previews()
    threads["ScreenSaver"].stop_screen_saver()
    threads["LedRingControl"].turn_off_all()
    logging.info("photobox is closing")


class Camera(Thread):
    global threads
    global capturedEvent
    #global videoPreviewEvent

    logger = logging.getLogger("Camera: ")

    startPreviewEvent = Event()
    startCapturingEvent = Event()

    def __init__(self):
        Thread.__init__(self)
        self.logger.info("initialisation")

        Thread.setName(self, "Camera")
        self.logger.info("name the Thread: Camera")


        self.startCapturing = False

        # Kill all gphoto2 processe

        subprocess.Popen('killall /usr/lib/gvfs/gvfs-gphoto2-volume-monitor', shell=True, stdout=False, stdin=False).wait()
        subprocess.Popen('killall /usr/lib/gvfs/gvfsd-gphoto2', shell=True, stdout=False, stdin=False).wait()


        #self.contex = gp.gp_context_new()
        #self.error, self.camera = gp.gp_camera_new()
        #self.error = gp.gp_camera_init(self.camera, self.contex)

        self._camera = gp.Camera()
        self._context = gp.gp_context_new()


        self.logger.debug("Want to open/initialize a connection to the Camera")

        try:
            gp.check_result(gp.gp_camera_init(self._camera, self._context))
            self.logger.debug("Succefully open/initialize a connection to the Camera")
        except gp.GPhoto2Error as gpe:
            self.logger.warning("GPhoto2Error Error: trying to open the connection to the Camera: %s", gpe)
        except Exception as e:
            self.logger.warning("Unkown Error: trying to open the connection to the Camera: %s", e)



        self.logger.debug('Camera summary: %s', str(self._camera.get_summary(self._context)))

        self.preview_is_running = False

    def run(self):

        while True:
            self.logger.debug("wait for startPreviewEvent")
            self.startPreviewEvent.wait()
            self.startPreviewEvent.clear()

            # preview
            self.logger.debug("execute _video_preview_process")
            self._video_preview_process()


            if(self.startCapturing):
                self.logger.debug("wait for startCapturingEvent")
                self.startCapturingEvent.wait()
                self.startCapturingEvent.clear()

                self.logger.debug("start capturing")
                self._capture()

                # wait for subProcess Picture Preview closed
                self.logger.debug("wait for capturedPreviewSubProcess")
                self.capturedPreviewSubProcess.wait()

    def start_video_preview(self):
        #global preview_is_running
        self.logger.debug("set the startPreviewEvent and set preview_is_running to True-> it should start")
        self.preview_is_running = True
        self.startPreviewEvent.set()

    def stop_video_preview(self):
        self.logger.debug("")
        self._stop_video_preview_process()

    def stop_captured_preview(self):
        self.logger.debug("")
        self._stop_captured_preview_process()

    def start_capturing(self):

        self.logger.debug("set startCapturingEvent -> it should start")
        self.startCapturing = True

        self._stop_video_preview_process()

        #Event().wait(1)

        self.startCapturingEvent.set()

    def stop_all_previews(self):
        #global preview_is_running

        self.logger.debug("")

        self._stop_video_preview_process()

        self._stop_captured_preview_process()

        self._close_connection_to_camera()

    def is_preview_video_running(self):
        #global preview_is_running
        self.logger.debug("return value from preview_is_running : %s", self.preview_is_running)
        return self.preview_is_running

    def _start_captured_preview_process(self):

        self.logger.debug("Start Picture preview")

        try:

            if(lastCapturedImage != noImageCapturedInfo):

                self.logger.debug("Open Captured in feh")
                picturePreviewCommand = "feh -xFY " + imageDirectory + lastCapturedImage
                self.capturedPreviewSubProcess = subprocess.Popen(picturePreviewCommand, shell=True, preexec_fn=os.setsid)

            else:
                self.logger.warning("Open noImageCapturedInfo Image in feh")
                picturePreviewCommand = "feh -xFY " + imageDirectory + lastCapturedImage
                self.capturedPreviewSubProcess = subprocess.Popen(picturePreviewCommand, shell=True, preexec_fn=os.setsid)
        except Exception as e:
            self.logger.warning("Error occurred, by the try to start the captured preview subprocess: $s", e)

    def _stop_captured_preview_process(self):

        try:
            # Send the signal to all the process groups
            os.killpg(os.getpgid(self.capturedPreviewSubProcess.pid), signal.SIGTERM)

            self.logger.debug("captured preview successful stopped")
        except Exception as e:
            self.logger.warning("Error occurred, by the try to stop the captured preview subprocess: $s", e)

    def _stop_video_preview_process(self):
        global devModus

        self.logger.debug("set The Variable preview_is_running to false")
        self.preview_is_running = False

        # Stop Subprocess Preview Stream
        try:
            if(devModus):
                os.killpg(os.getpgid(self.videoPreviewSubProcess.pid), signal.SIGTERM)
            else:
                self.videoPreviewSubProcess.stdin.write("quit()".encode())
                os.killpg(os.getpgid(self.videoPreviewSubProcess.pid), signal.SIGTERM)
            self.logger.debug("video preview process successful stopped")
        except Exception as e:
            self.logger.warning("Error occurred, by the try to stop the video preview subprocess: $s", e)


        self.logger.debug("Stop Camera video preview")

    def _video_preview_process(self):
        global video_preview_fps

        self.logger.debug("clear the startPreviewEvent")
        self.startPreviewEvent.clear()

        # Subprocess Preview Stream
        first = True

        self.logger.debug("Start Camera preview")
        self.logger.debug("preview_is_running: %s", self.preview_is_running)

        if(devModus):
            videoPreviewCommand = "feh '" + imageDirectory + "pre.jpg'"
            self.videoPreviewSubProcess = subprocess.Popen(videoPreviewCommand, shell=True, preexec_fn=os.setsid)

        else:
            while self.preview_is_running:

                try:

                    camera_file = gp.check_result(gp.gp_camera_capture_preview(self._camera))

                    data_file = gp.check_result(gp.gp_file_get_data_and_size(camera_file))

                    image = Image.open(io.BytesIO(data_file))
                    image.save("tmp.jpg")


                    if first:
                        try:
                            videoPreviewCommand = "pqiv --actions-from-stdin -fit tmp.jpg"
                            self.videoPreviewSubProcess = subprocess.Popen(videoPreviewCommand, shell=True, preexec_fn=os.setsid,
                                                                        stdin=subprocess.PIPE)
                            first = False
                        except Exception as e:
                            self.logger.warning("Cannot start pqiv: %s ", e)
                    else:
                        self.videoPreviewSubProcess.stdin.write("reload()".encode())

                except gp.GPhoto2Error as gpe:
                    self.logger.warning("Error no picture could be maked, reason GPhoto2Error: %s", gpe)

                except Exception as e:
                    self.logger.warning("Error no picture could be maked, reason unkown: %s", e)


                time.sleep(1/video_preview_fps)

        self.logger.debug("wait 0.1 sec")
        Event().wait(0.1)

        #self._close_connection_to_camera()
        self.logger.debug("video preview is stopped now")

    def _capture(self):
        global captured
        global lastCapturedImage
        global capturedEvent


        self.startCapturing = False

        # Subprocess Camera Capturing
        date = time.strftime("%Y-%m-%d-%H-%M-%S")
        # fileName = date + str(hashedName) + imageFileType
        lastCapturedImage = date + "." + imageFileType
        self.logger.debug("Save the new Image in %s", imageDirectory + lastCapturedImage)

        # TODO better name
        captured = True

        try:

            camera_file = gp.check_result(gp.gp_camera_capture(self._camera, gp.GP_CAPTURE_IMAGE))

            data_file = gp.check_result(gp.gp_camera_file_get(self._camera, camera_file.folder, camera_file.name, gp.GP_FILE_TYPE_NORMAL))

            data_file = gp.check_result(gp.gp_file_get_data_and_size(data_file))

            image = Image.open(io.BytesIO(data_file))
            image.save((imageDirectory + lastCapturedImage))


            checkImg = Image.open(imageDirectory + lastCapturedImage)
            self.logger.debug("Image captured and saved correctly")
            image.save("tmp.jpg")

        except gp.GPhoto2Error as gpe:
            self.logger.warning("Error no picture could be maked, reason GPhoto2Error: %s", gpe)

            lastCapturedImage = noImageCapturedInfo


        except Exception as e:
            self.logger.warning("Error no picture could be maked, reason unkown: %s", e)

            self.logger.debug("Image cant captured or saved: %s", e)
            os.remove(imageDirectory + lastCapturedImage)

            lastCapturedImage = noImageCapturedInfo

        self._close_connection_to_camera()

        # start preview Subprocess
        self._start_captured_preview_process()

        capturedEvent.set()

    def _close_connection_to_camera(self):
        self.logger.debug("Want to close/exit the connection to the Camera")
        try:
            gp.check_result(gp.gp_camera_exit(self._camera, self._context))
            self.logger.debug("Succefully close/exit the connection to the Camera")
        except gp.GPhoto2Error as gpe:
            self.logger.warning("GPhoto2Error Error: trying to close the connection to the Camera: %s", gpe)
        except Exception as e:
            self.logger.warning("Unkown Error: trying to close the connection to the Camera: %s", e)


class ScreenSaver(Thread):
    global threads
    startScreenSaverEvent = Event()
    diashowDelayEvent = Event()



    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "ScreenSaver")

        self.startScreenSaverEvent.set()
        self.lastInteraction = time.time()


    def run(self):

        while True:
            self.startScreenSaverEvent.wait(screenSaverStartTimer - (time.time() - self.lastInteraction))

            if(time.time() - self.lastInteraction  > screenSaverStartTimer):
                self.start_screen_saver()

            if(self.startScreenSaverEvent.is_set()):
                self.diashow()

    def start_screen_saver(self):
        global captured

        self.startScreenSaverEvent.set()
        self.diashowDelayEvent.clear()

        # Save Image
        saveImage()

        captured = False

        threads['Camera'].stop_all_previews()

    def stop_screen_saver(self):
        self.startScreenSaverEvent.clear()
        self.diashowDelayEvent.set()

    def is_set(self):
        return self.startScreenSaverEvent.is_set()

    def update_last_interaction(self):
        self.lastInteraction = time.time()

    def diashow(self):
        global diashowTime


        self.globalPictures = glob.glob(imageDirectory + '*.' + imageFileType)

        while not self.diashowDelayEvent.is_set():

            if(len(self.globalPictures) == 0):
                imageViewCommand = 'feh -xFY ' + noImageFound

            else:
                #imageViewCommand = 'feh -xFY ' + tmpDisplayImage
                #imageViewCommand = 'raspidmx/pngview/pngview -b 0 -l 3 -t 10000 ' + tmpDisplayImage

                imageViewCommand = 'cd ' + imageDirectory + '; feh -xFYz -D ' + str(diashowTime)

            pro = subprocess.Popen(imageViewCommand, shell=True, preexec_fn=os.setsid)

            self.diashowDelayEvent.wait()
            os.killpg(os.getpgid(pro.pid), signal.SIGTERM)

    def stock_photos(self):
        pass


class LedRingControl(Thread):
    global threads

    ledCountdownEvent = Event()

    # TODO add LED variables
    ledPixels = 24

    pixels = neopixel.NeoPixel(ledCyclePin, ledPixels)

    startindex = 1
    endindex = 23

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "LedRingControl")


    def run(self):

        self.led_ring_function_rainbow_cycle(0.001)

        while True:
            self.ledCountdownEvent.wait()

            self.led_ring_function_countdown(10)
            #self.led_ring_function_rainbow_cycle(10)


    # local
    def increase_led_ring(self):
        pass

    # local
    def reset_led_ring(self):
        pass

    def led_ring_function_countdown(self, wait_for_barrier=False):

        if wait_for_barrier:
            global sync_Countdown_Barrier
            self.logger.debug("Wait on a Barrier for the Countdown Thread to start the coutdown synchron")
            sync_Countdown_Barrier.wait()

        # TODO break condition
        #while(countdown > 0):
            #self.increase_led_ring()
        for i in range(10, 0, -1):

            if False and self.startindex != 6 and self.startindex != 12 and self.endindex != 18 and self.endindex != 24:
                self.pixels[self.startindex] = (255, 255, 255)
                self.pixels[self.endindex] = (255, 255, 255)

                Event().wait(1)

            self.startindex += 1
            self.endindex -= 1


        # TODO wait for: capture finished

    def wheel(self, pos):
        # Input a value 0 to 255 to get a color value.
        # The colours are a transition r - g - b - back to r.
        if pos < 0 or pos > 255:
            r = g = b = 0
        elif pos < 85:
            r = int(pos * 3)
            g = int(255 - pos * 3)
            b = 0
        elif pos < 170:
            pos -= 85
            r = int(255 - pos * 3)
            g = 0
            b = int(pos * 3)
        else:
            pos -= 170
            r = 0
            g = int(pos * 3)
            b = int(255 - pos * 3)
        return (r, g, b) if ORDER == neopixel.RGB or ORDER == neopixel.GRB else (r, g, b, 0)
    '''
    def led_ring_function_rainbow_cycle(self, speed):
        # rgb LED got three, 8bit colors
        # red   0 - 255
        # green 0 - 255
        # blue  0 - 255
        red = 0
        green = 0
        blue = 0
        max = 255

        led =  0

        for j in range(255):
            for i in range(self.ledPixels):
                pixel_index = int()(i * 256 / self.ledPixels) + j
                self.pixels[i] = self.wheel(pixel_index & 255)
            self.pixels.show()
            time.sleep(speed)
    '''
    def led_ring_function_rainbow_cycle(self, wait):
        r = 0
        g = 0
        b = 0
        steps = 20
        reverse = False
        mini = 30
        for j in range(10):
            for i in range(self.ledPixels):
                self.pixels[i] = (r, g, b)
                if not reverse:

                    if r < 255:
                        r += steps
                        if r > 255:
                            r = 255
                    elif g < 255:
                        g += steps
                        if g > 255:
                            g = 255
                    elif b < 255:
                        b += steps
                        if b > 255:
                            b = 255
                            reverse = True
                else:
                    if r > mini:
                        r -= steps
                        if r < mini:
                            r = mini
                    elif g > mini:
                        g -= steps
                        if g < mini:
                            g = mini
                    elif b > mini:
                        b -= steps
                        if b < mini:
                            b = mini
                            reverse = False

                time.sleep(wait)
        self.pixels.fill((0, 0, 0))



    def start_led_countdown_event(self):
        self.ledCountdownEvent.set()

    def stop_led_countdown_event(self):
        self.ledCountdownEvent.clear()

    def set_led_color(self, ledNumber, rgb):
        self.pixels[ledNumber] = (rgb[0], rgb[1], rgb[2])

    def set_led_on(self, ledNumber):
        pass

    def set_led_off(self, ledNumber):
        pass

    def turn_off_all(self):
        self.pixels.fill((0, 0, 0))


class Countdown(Thread):
    global threads
    countdownEvent = Event()
    logger = logging.getLogger(__name__)

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "Countdown")


    def run(self):
        while True:
            self.countdownEvent.wait()

            if(threads["Camera"].is_preview_video_running()):
                self._countdown(10, False)
                #threads["LedRingControl"].start_led_countdown_event(False)

    def start_countdown(self):
        self.countdownEvent.set()
        #time.sleep(0.3)
        self.countdownEvent.clear()

    # local function
    def _countdown(self, time, wait_for_barrier=False):
        if wait_for_barrier:
            global sync_Countdown_Barrier
            self.logger.debug("Wait on a Barrier for the LED Thread to start the coutdown synchron")
            sync_Countdown_Barrier.wait()

        for i in range(time, 0, -1):

            try:
                if (i == 2):
                    # Der Boolean wird auf True gesetzt es wird auf das wait vom Preview stream Subprocess gewartet
                    threads["Camera"].start_capturing()

                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 4 -t 2000 ' + path[0] + "/Files/smilePictures/pleaseSmile.png"

                    subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE)

                if(devModus):
                    
                    self.logger.debug("Picture: " + str(i))
                    Event().wait(1)
                else:
                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 3 -t 1000 ' + path[0] + "/Files/counterPictures/counterWhite/" + str(i) + '.png'

                    subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE).wait()

            except Exception as e:
                self.logger.debug("Error programm pngview or counter file not found: %s", e)
                self.logger.debug("Error happend by i: %s", i)



def getButton():
    inputCommand = ""


    while(inputCommand == ""):

        Event().wait(0.1)

        if (captureButton.is_pressed):
            inputCommand = 'c'
            captureButton.wait_for_release()

        if (reCaptureButton.is_pressed):
            inputCommand = 'r'
            reCaptureButton.wait_for_release()

        if (abortButton.is_pressed):
            inputCommand = 'a'
            abortButton.wait_for_release()


    return inputCommand


def saveImage():
    global lastCapturedImage
    if(lastCapturedImage != noImageCapturedInfo):

        try:
            if(saveOnServer):
                os.rename(imageDirectory + lastCapturedImage, serverImageDirectory + lastCapturedImage)

                logging.debug("Image saved on server")
        except:
            logging.warning("Error: Image cant be moved")

    lastCapturedImage = ""


def deleteImage():
    global lastCapturedImage

    if(lastCapturedImage != noImageCapturedInfo):

        try:
            os.remove(imageDirectory + lastCapturedImage)
            logging.debug("Image delete")
        except:
            logging.warning("Error: Image cant be delete")

        #Event().wait(0.5)

    lastCapturedImage = ""


if __name__ == '__main__':

    # if the program close all processes will be closed
    atexit.register(exit_handler)
    signal.signal(signal.SIGINT, exit_handler)

    Event().wait(10)

    cameraThread = Camera()
    cameraThread.start()

    countdownThread = Countdown()
    countdownThread.start()

    screenSaverThread = ScreenSaver()
    screenSaverThread.start()

    ledRing1Thread = LedRingControl()
    ledRing1Thread.start()

    # TODO documentation fehlt, was macht das thread.update

    threads.update({cameraThread.getName(): cameraThread})
    threads.update({countdownThread.getName(): countdownThread})
    threads.update({screenSaverThread.getName(): screenSaverThread})
    threads.update({ledRing1Thread.getName(): ledRing1Thread})



    # Main Event
    while True:
        button = getButton()
        logging.info("Button: %s is pressed", button)
        #button = input("Please enter: ")
        screenSaverThread.update_last_interaction()

        if(screenSaverThread.is_set()):
            screenSaverThread.stop_screen_saver()

            cameraThread.start_video_preview()

        elif(button == "c"):
            if(captured):
                # Close the previewPictureProcess
                cameraThread.stop_captured_preview()

                # Save Image
                saveImage()

                captured = False

                cameraThread.start_video_preview()

            else:
                # Start countdown
                countdownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()

        elif(button == "r"):
            if(captured):
                # Close the previewPictureProcess
                cameraThread.stop_captured_preview()

                # Save Image
                saveImage()

                captured = False

                cameraThread.start_video_preview()

                # Start countdown
                countdownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()

        elif(button == "a"):
            if(captured):
                # Close the previewPictureProcess
                cameraThread.stop_captured_preview()

                deleteImage()

                captured = False

                cameraThread.start_video_preview()

        else:
            logging.warning("Wrong Input: %s", button)
