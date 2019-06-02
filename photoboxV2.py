'''
    This is a PhotoBox Software

    @author Lars Stratmann
    @Version 2.0
    @modified: 2019.08.05
'''

from threading import Thread, Event, Lock
import threading
import time
import subprocess

threads = {}
captured = False
pictureLocation = ""

pictureLocationLock = Lock()
capturedEvent = Event()

# TODO Subprocess preview
picturePreviewSubProcess = None

class Camera(Thread):
    global threads
    global capturedEvent



    startPreviewEvent = Event()

    finishCaptureEvent = Event()

    startCapturing = False

    picturePreviewSubProcess = None

    tmp1Event = Event()

    # TODO subProcess Var for the preview Stream
    #previewStream = ""

    def __init__(self):
        Thread.__init__(self)

        Thread.setName(self, "Camera")

    def run(self):
        while True:
            self.startPreviewEvent.wait()

            # preview
            self.start_preview_process()

            # TODO wait for subProcess Camera Stream closed
            self.tmp1Event.wait()

            if(self.startCapturing):
                self.capture()

                # Das Event brauchen wir vllt nicht wenn wir die wait Funktion des Subprocess nutzen
                self.finishCaptureEvent.wait()


    def start_preview(self):
        self.startPreviewEvent.set()

    def stop_preview(self):
        self.startPreviewEvent.clear()

        self.stop_preview_process()

        # TODO Only for TEST
        self.tmp1Event.set()
        self.tmp1Event.clear()

    def start_capturing(self):
        self.startCapturing = True

    def is_set(self):
        return self.startPreviewEvent.is_set()

    def start_picture_preview(self):
        self.picturePreviewSubProcess = subprocess.Popen('vlc', shell=True, stdin=subprocess.PIPE)

    def stop_picture_preview(self):
        self.picturePreviewSubProcess.close()

    # local function
    def start_preview_process(self):

        # TODO Subprocess Preview Stream
        print("Start Camera preview, need implementation")


    # local function
    def stop_preview_process(self):

        # TODO Stop Subprocess Preview Stream
        print("Stop Camera preview, need implementation")


    # local function
    def capture(self):
        # TODO Subprocess Camera Capturing

        self.captured = True

        # TODO start preview Subprocess
        self.start_picture_preview()

        capturedEvent.set()


class ScreenSaver(Thread):
    global threads
    startScreenSaverEvent = Event()
    diashowDelay = Event()

    # in seconds
    screenSaverStartTime = 30


    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "ScreenSaver")

        self.startScreenSaverEvent.set()
        self.lastInteraction = time.time()


    def run(self):

        while True:
            # TODO testen ob Probleme fuer negativ Werte aufftreten
            self.startScreenSaverEvent.wait(self.screenSaverStartTime - (time.time() - self.lastInteraction))

            if(time.time() - self.lastInteraction  > self.screenSaverStartTime):
                self.start_screen_saver()

            if(self.startScreenSaverEvent.is_set()):
                self.diashow()

    def start_screen_saver(self):
        self.startScreenSaverEvent.set()
        self.diashowDelay.clear()

        threads['Camera'].stop_preview()

    def stop_screen_saver(self):
        self.startScreenSaverEvent.clear()
        self.diashowDelay.set()

    def is_set(self):
        return self.startScreenSaverEvent.is_set()

    def update_last_interaction(self):
        self.lastInteraction = time.time()

    def diashow(self):

        while not self.diashowDelay.is_set():
            # TODO show Picutres
            print("Diashow")
            self.diashowDelay.wait(5)

    def stock_photos(self):
        pass


class LedControl(Thread):
    global threads

    def __init__(self):
        Thread.__init__(self)
        Thread.setName(self, "LedControl")


    def run(self):
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
                    threads["Camera"].stop_preview()

                    print("Preview Thread stoped")

                #counterCommand = '/home/pi/raspidmx/pngview/pngview -b 0 -l 3 -t 1000 ' + counterPath + str(i) + '.png'

                #subprocess.Popen(counterCommand, shell=True, stdout=False, stdin=subprocess.PIPE).wait()
                print("Picture: " + str(i))
                Event().wait(1)
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




if __name__ == '__main__':

    cameraThread = Camera()
    cameraThread.start()

    countDownThread = Countdown()
    countDownThread.start()

    screenSaverThread = ScreenSaver()
    screenSaverThread.start()

    threads.update({cameraThread.getName(): cameraThread})
    threads.update({countDownThread.getName(): countDownThread})
    threads.update({screenSaverThread.getName(): screenSaverThread})



    # Main Event
    while True:
        #button = getButton()
        button = input("Please enter: ")
        screenSaverThread.update_last_interaction()


        if(captured):
            cameraThread.stop_picture_preview()


        # ScreenSave Thread stop
        if(screenSaverThread.is_set()):
            # TODO Stop screenSaver
            screenSaverThread.stop_screen_saver()

            # TODO Start Preview
            cameraThread.start_preview()

        elif(button == "c"):
            if(captured):
                # TODO Close the previewPictureProcess

                # TODO Save Image

                captured = False

            else:
                # Start countdown
                countDownThread.start_countdown()
                capturedEvent.wait()
                capturedEvent.clear()


        elif(button == "r"):
            if(captured):
                # TODO Close the previewPictureProcess

                # TODO Save Image
                # TODO Start countdown

                captured = False

        elif(button == "a"):
            if(captured):
                # TODO Close the previewPictureProcess

                # TODO Delete Image
                captured = False

        else:
            print("Wrong Input")
