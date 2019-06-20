'''
    This is a PhotoBox Software

    @author Lars Stratmann
    @Version 2.0
    @modified: 20.06.2019

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

    TODO Preview Picture subprocess FIX

    TODO add the subprocess for the Camera

    TODO Captured Image Check

    TODO LedControl

    TODO pngview check implement
'''

from threading import Thread, Event, Lock
import time
import subprocess
import os
import signal
import glob
import random
from PIL import Image

# boolean for Develop Modus
devModus = True

threads = {}
captured = False
imageDirectory = "/home/lars/Bilder/"
imageFileType = "jpg"
lastCapturedImage = "tmp.jpg"

noImageCapturedInfo = "Files/keinFotofuerDich2.jpg"


saveOnServer = False
serverImageDirectory = ""


# The Time how long a picture will be show
diashowTime = 5


captureButton = None
saveButton = None
abortButton = None

# in seconds
screenSaverStartTime = 30

pictureLocationLock = Lock()
capturedEvent = Event()



# TODO Subprocess preview
picturePreviewSubProcess = None

class Camera(Thread):
    global threads
    global capturedEvent

    startPreviewEvent = Event()

    finishCaptureEvent = Event()

    def __init__(self):
        Thread.__init__(self)

        Thread.setName(self, "Camera")

        self.startCapturing = False

        subprocess.Popen('mkfifo fifo.mjpg', shell=True, stdout=False, stdin=subprocess.PIPE).wait()

        # Kill all gphoto2 processes
        subprocess.Popen('killall /usr/lib/gvfs/gvfs-gphoto2-volume-monitor', shell=True, stdout=False, stdin=False).wait()
        subprocess.Popen('killall /usr/lib/gvfs/gvfsd-gphoto2', shell=True, stdout=False, stdin=False).wait()


    def run(self):
        while True:
            self.startPreviewEvent.wait()

            # preview
            self.start_video_preview_process()

            # wait for subProcess Camera Stream closed
            self.videoPreviewSubProcess.wait()

            if(self.startCapturing):
                self.capture()

                # Das Event brauchen wir vllt nicht wenn wir die wait Funktion des Subprocess nutzen
                #self.finishCaptureEvent.wait()

                # wait for subProcess Picture Preview closed
                self.picturePreviewSubProcess.wait()


    def start_preview(self):
        self.startPreviewEvent.set()

    def stop_preview(self):
        self.startPreviewEvent.clear()

        self.stop_video_preview_process()

        self.stop_picture_preview_process()


    def start_capturing(self):

        self.startCapturing = True

        self.stop_video_preview_process()


    def is_set(self):
        return self.startPreviewEvent.is_set()

    def start_picture_preview_process(self):

        picturePreviewCommand = "feh -xFY " + lastCapturedImage

        # The os.setsid() is passed in the argument preexec_fn so
        # it's run after the fork() and before  exec() to run the shell.
        self.picturePreviewSubProcess = subprocess.Popen(picturePreviewCommand, shell=True, preexec_fn=os.setsid)

        print("Start Picture preview")


    def stop_picture_preview_process(self):

        # Send the signal to all the process groups
        os.killpg(os.getpgid(self.picturePreviewSubProcess.pid), signal.SIGTERM)
        print("Stop Picture preview")


    # local function
    def start_video_preview_process(self):

        # TODO Subprocess Preview Stream

        if(devModus):
            videoPreviewCommand = "feh '" + imageDirectory + "pre.jpg'"

        else:
            videoPreviewCommand = "gphoto2 --capture-movie --stdout > fifo.mjpg & omxplayer --layer 2 -b --live fifo.mjpg"

        # The os.setsid() is passed in the argument preexec_fn so
        # it's run after the fork() and before  exec() to run the shell.
        self.videoPreviewSubProcess = subprocess.Popen(videoPreviewCommand, shell=True, preexec_fn=os.setsid)

        print("Start Camera preview, need implementation")

        Event().wait(0.3)


    # local function
    def stop_video_preview_process(self):

        # TODO Stop Subprocess Preview Stream
        os.killpg(os.getpgid(self.videoPreviewSubProcess.pid), signal.SIGTERM)

        print("Stop Camera video preview")


    # local function
    def capture(self):
        global captured
        global lastCapturedImage

        # TODO Subprocess Camera Capturing
        date = time.strftime("%Y-%m-%d-%H-%M-%S")
        # fileName = date + str(hashedName) + imageFileType
        lastCapturedImage = date + imageFileType

        captureCommmand = "gphoto2 --keep --capture-image-and-download --stdout > " + lastCapturedImage

        subprocess.Popen(captureCommmand, shell=True, stdout=False, stdin=False).wait()
        captured = True

        try:
            lastCapturedImage = imageDirectory + lastCapturedImage

            checkImg = Image.open(lastCapturedImage)
            print("Image captured")

        except:
            print("Image cant captured")
            os.remove(lastCapturedImage)

            lastCapturedImage = noImageCapturedInfo


        # TODO start preview Subprocess
        self.start_picture_preview_process()

        capturedEvent.set()


class ScreenSaver(Thread):
    global threads
    startScreenSaverEvent = Event()
    diashowDelayEvent = Event()



    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "ScreenSaver")

        self.startScreenSaverEvent.set()
        self.lastInteraction = time.time()

        self.globalPictures = glob.glob('*.' + imageFileType)


    def run(self):

        while True:
            # TODO testen ob Probleme fuer negativ Werte aufftreten
            self.startScreenSaverEvent.wait(screenSaverStartTime - (time.time() - self.lastInteraction))

            if(time.time() - self.lastInteraction  > screenSaverStartTime):
                self.start_screen_saver()

            if(self.startScreenSaverEvent.is_set()):
                self.diashow()

    def start_screen_saver(self):
        self.startScreenSaverEvent.set()
        self.diashowDelayEvent.clear()

        threads['Camera'].stop_preview()

    def stop_screen_saver(self):
        self.startScreenSaverEvent.clear()
        self.diashowDelayEvent.set()

    def is_set(self):
        return self.startScreenSaverEvent.is_set()

    def update_last_interaction(self):
        self.lastInteraction = time.time()

    def diashow(self):


        self.globalPictures = glob.glob(imageDirectory + '*.' + imageFileType)

        while not self.diashowDelayEvent.is_set():
            # TODO show Picutres
            print("Diashow")

            tmpDisplayImage = str(self.globalPictures[random.randint(0, len(self.globalPictures) - 1)])

            if(devModus):

                pro = subprocess.Popen("feh '" + tmpDisplayImage + "'", shell=True, preexec_fn=os.setsid)


                self.diashowDelayEvent.wait(5)

                os.killpg(os.getpgid(pro.pid), signal.SIGTERM)

            else:
                imageViewCommand = '../raspidmx/pngview/pngview -b 0 -l 3 -t 5000 ' + imageDirectory + tmpDisplayImage

                subprocess.Popen(imageViewCommand, shell=True).wait()

    def stock_photos(self):
        pass


class LedRingControl(Thread):
    global threads

    ledCountdownEvent = Event()

    # TODO add LED variables
    ledPins = 12

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "LedRingControl")


    def run(self):
        while True:
            self.ledCountdownEvent.wait()

            self.led_ring_function()


    # local
    def increase_led_ring(self):
        pass

    # local
    def reset_led_ring(self):
        pass

    def led_ring_function(self, countdown):

        while(countdown > 0):
            self.increase_led_ring()

            countdown -= 1
            Event().wait(1)

        # TODO wait for: capture finished


    def start_led_countdown_event(self):
        self.ledCountdownEvent.set()

    def stop_led_countdown_event(self):
        self.ledCountdownEvent.clear()

    def set_led_on(self, ledNumber):
        pass

    def set_led_off(self, ledNumber):
        pass


class Countdown(Thread):
    global threads
    countdownEvent = Event()

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "Countdown")


    def run(self):
        while True:
            self.countdownEvent.wait()

            if(threads["Camera"].is_set()):
                self.countdown(10)

    def start_countdown(self):
        self.countdownEvent.set()
        #time.sleep(0.3)
        self.countdownEvent.clear()

    # local function
    def countdown(self, time):
        for i in range(time, 0, -1):

            try:
                if (i == 2):
                    # TODO clear previewEvent and start capture
                    # Der Boolean wird auf True gesetzt es wird auf das wait vom Preview stream Subprocess gewartet
                    threads["Camera"].start_capturing()
                    #threads["Camera"].stop_preview()

                if(devModus):
                    print("Picture: " + str(i))
                    Event().wait(1)
                else:
                    counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 3 -t 1000 ' + imageDirectory + str(i) + '.png'

                    subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE).wait()

            except:
                print("Error programm pngview or counter file not found")


def getButton():
    inputCommand = ""
    if (captureButton.wait_for_press() or saveButton.wait_for_press() or abortButton.wait_for_press()):
        if (captureButton.is_pressed):
            inputCommand = 'c'
            captureButton.wait_for_release()

        elif (saveButton.is_pressed):
            inputCommand = 's'
            saveButton.wait_for_release()

        elif (abortButton.ispressed):
            inputCommand = 'a'
            saveButton.wait_for_release()
        else:
            inputCommand = "nothing"

    return inputCommand

# TODO add function
def saveImage():
    global lastCapturedImage
    if(lastCapturedImage != noImageCapturedInfo):

        try:
            if(saveOnServer):
                os.rename(imageDirectory + lastCapturedImage, serverImageDirectory + lastCapturedImage)

            print("Image saved")
        except:
            print("Error: Image cant be moved")

    lastCapturedImage = ""

# TODO add function
def deleteImage():
    global lastCapturedImage

    if(lastCapturedImage != noImageCapturedInfo):

        try:
            os.remove(imageDirectory + lastCapturedImage)
            print("Image delete")
        except:
            print("Error: Image cant be delete")

        Event().wait(1)

    lastCapturedImage = ""

if __name__ == '__main__':

    cameraThread = Camera()
    cameraThread.start()

    countdownThread = Countdown()
    countdownThread.start()

    screenSaverThread = ScreenSaver()
    screenSaverThread.start()

    threads.update({cameraThread.getName(): cameraThread})
    threads.update({countdownThread.getName(): countdownThread})
    threads.update({screenSaverThread.getName(): screenSaverThread})



    # Main Event
    while True:
        #button = getButton()
        button = input("Please enter: ")
        screenSaverThread.update_last_interaction()


        #if(captured):
        #    cameraThread.stop_picture_preview_process()


        # ScreenSaver Thread stop
        if(screenSaverThread.is_set()):
            # TODO Stop screenSaver
            screenSaverThread.stop_screen_saver()

            # TODO Start Preview
            cameraThread.start_preview()

        elif(button == "c"):
            if(captured):
                # TODO Close the previewPictureProcess
                cameraThread.stop_picture_preview_process()

                # TODO Save Image
                saveImage()

                captured = False

            else:
                # Start countdown
                countdownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()


        elif(button == "r"):
            if(captured):
                # TODO Close the previewPictureProcess
                cameraThread.stop_picture_preview_process()

                # TODO Save Image
                saveImage()

                captured = False

                Event().wait(1)

                # TODO Start countdown
                # Start countdown
                countdownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()


        elif(button == "a"):
            if(captured):
                # TODO Close the previewPictureProcess
                cameraThread.stop_picture_preview_process()

                deleteImage()
                captured = False

        else:
            print("Wrong Input")
