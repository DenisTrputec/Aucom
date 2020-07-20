import sys
import wave
import pyaudio
import librosa as lr
import numpy as np
from os import path
from math import floor, ceil
from PyQt5 import QtWidgets, QtCore, QtGui, uic

# Global variables
period = 0.75
diff = 0.2
noise = 0.001


class AudioFile:
    def __init__(self, file_path):
        try:
            audio, sfreq = lr.load(file_path)
            self.audio = audio
            self.time = np.arange(0, len(audio)) / sfreq
            self.intervals = self.findNoSoundIntervals()
        except BaseException as e:
            error_dialog = QtWidgets.QMessageBox()
            error_dialog.setIcon(QtWidgets.QMessageBox.Critical)
            error_dialog.setWindowTitle("Error")
            error_dialog.setText("Error while reading audio file!")
            error_dialog.setDetailedText(f'{e}')
            error_dialog.exec_()

    def findNoSoundIntervals(self):
        interval_list = []  # List of tupples
        start = None  # Time when no sound interval started
        no_sound = False  # Flag if there was a sound
        for t, a in zip(self.time, self.audio):
            if noise * (-1) < a < noise:  # If there isn't sound
                if no_sound is False:
                    start = round(t, 1)
                    no_sound = True
            else:
                if no_sound is True:
                    if t > start + period:
                        # m1, s1 = divmod(start, 60)
                        # m2, s2 = divmod(round(t, 1), 60)
                        # print(f"No sound from {m1:02.0f}:{s1:04.1f} to {m2:02.0f}:{s2:04.1f}")
                        # print("No sound from " + str(start) + " to " + str(round(t, 1)))
                        interval_list.append((start, round(t, 1)))
                    no_sound = False
        return interval_list


class AudioPlayer:
    def __init__(self):
        self.chunk = 1024
        self.wf = None
        self.pa = None
        self.stream = None
        self.playing = False

    def read(self, filename):
        # Open the sound file and create interface to PortAudio
        self.wf = wave.open(filename, 'rb')
        self.pa = pyaudio.PyAudio()

        # Open a .Stream object to ertie the WAV file to
        # 'output=true' indicates that the sound will be player rather than recorded
        self.stream = self.pa.open(format=self.pa.get_format_from_width(self.wf.getsampwidth()),
                                   channels=self.wf.getnchannels(),
                                   rate=self.wf.getframerate(),
                                   output=True)

    def play_all(self):
        # Read data in chunks
        data = self.wf.readframes(self.chunk)

        # Currently playing
        self.playing = True

        # Play the sound by writing the audio data to the stream
        while data != '' and self.playing:
            self.stream.write(data)
            data = self.wf.readframes(self.chunk)

        # Close and terminate the stream
        self.stream.close()
        self.pa.terminate()

    def play(self, timestring):
        # Get start and length from time string
        start = floor(float(timestring[5:7]) * 60 + float(timestring[8:12]))
        length = ceil(float(timestring[16:18]) * 60 + float(timestring[19:23]) - start)

        # Skip unwanted frames
        n_frames = int(start * self.wf.getframerate())
        self.wf.setpos(n_frames)

        # Write desired framres to audio buffer
        n_frames = int(length * self.wf.getframerate())
        frames = self.wf.readframes(n_frames)
        self.stream.write(frames)

        self.stream.close()
        self.pa.terminate()
        self.wf.close()


class LoadingScreen(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(200, 200)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.CustomizeWindowHint)

        self.label_info = QtWidgets.QLabel(self)
        self.label_animation = QtWidgets.QLabel(self)
        self.movie = QtGui.QMovie("Loading_2.gif")
        self.label_animation.setMovie(self.movie)
        # self.a = QtWidgets.QPushButton(self)
        # self.a.setDisabled(True)

    def startAnimation(self):
        self.show()
        self.movie.start()

    def stopAnimation(self):
        self.movie.stop()
        self.hide()


class Aucom(QtWidgets.QMainWindow):
    def __init__(self):
        super(Aucom, self).__init__()

        uic.loadUi('aucom.ui', self)

        self.org_audio = None
        self.dub_audio = None
        self.player = AudioPlayer()

        # self.loading_screen = LoadingScreen()

        self.pushButton_Original.clicked.connect(self.browse)
        self.pushButton_Dub.clicked.connect(self.browse)
        self.pushButton_Compare.clicked.connect(self.compare)
        self.action_OriginalAudio.triggered.connect(self.play_all)
        self.pushButton_Play.clicked.connect(self.play)

    def browse(self):
        file_path = QtWidgets.QFileDialog.getOpenFileName(self, caption='Choose audio file', directory='',
                                                          filter='*.wav')
        sender = self.sender()
        if sender.objectName() == 'pushButton_Original':
            self.lineEdit_Original.setText(file_path[0])
        else:
            self.lineEdit_Dub.setText(file_path[0])

    def compare(self):
        if path.exists(self.lineEdit_Original.text()) and path.exists(self.lineEdit_Dub.text())\
                and (self.lineEdit_Original.text()).endswith(".wav") and (self.lineEdit_Dub.text()).endswith(".wav"):

            self.pushButton_Compare.setDisabled(True)
            updateLabel(self.label_Progress, "Reading original audio...")
            self.org_audio = AudioFile(self.lineEdit_Original.text())
            updateLabel(self.label_Progress, "Reading dubbed audio...")
            self.dub_audio = AudioFile(self.lineEdit_Dub.text())
            updateLabel(self.label_Progress, "Comparing audio files...")
            self.compare_intervals()
            updateLabel(self.label_Progress, "")
            self.pushButton_Compare.setDisabled(False)

        else:
            error_dialog = QtWidgets.QMessageBox()
            error_dialog.setIcon(QtWidgets.QMessageBox.Warning)
            error_dialog.setWindowTitle("Warning")
            error_dialog.setText("No files to compare!")
            error_dialog.setInformativeText("At least one file is not selected.")
            error_dialog.setDetailedText("File must be in Waveform Audio File Format (*.wav)")
            error_dialog.exec_()

    def compare_intervals(self):
        self.listWidget_Gaps.clear()
        output = []
        i1 = i2 = 0
        while i1 < len(self.org_audio.intervals) - 1 and i2 < len(self.dub_audio.intervals):
            a_left, a_right = self.org_audio.intervals[i1]
            b_left, b_right = self.org_audio.intervals[i1 + 1]
            c_left, c_right = self.dub_audio.intervals[i2]

            if c_left >= a_right - diff and c_right <= b_left + diff:
                output.append((c_left, c_right))
            elif c_left < b_left - diff and c_right > a_right + diff:
                output.append((c_left if c_left > a_right else a_right, b_left))
            # Check for last one only
            if self.dub_audio.intervals[i2] == self.dub_audio.intervals[len(self.dub_audio.intervals) - 1] \
                    and self.org_audio.intervals[i1] == self.org_audio.intervals[len(self.org_audio.intervals) - 2]:
                if c_left + diff <= b_right <= c_right - diff:
                    output.append((b_right, c_right))

            if c_left > b_left:
                i1 += 1
            else:
                i2 += 1

        for o in output:
            o1, o2 = o
            m1, s1 = divmod(o1, 60)
            m2, s2 = divmod(o2, 60)
            self.listWidget_Gaps.addItem(f"From {m1:02.0f}:{s1:04.1f} to {m2:02.0f}:{s2:04.1f}")

        self.listWidget_Gaps.update()

    def play_all(self):
        filename = self.lineEdit_Original.text()
        self.player.read(filename)
        self.player.play_all()

    def play(self):
        # q = QtWidgets.QPushButton()
        # q.objectName()
        # print(self.listWidget_Gaps.currentItem().text())
        self.player.read(self.lineEdit_Original.text())
        self.player.play(self.listWidget_Gaps.currentItem().text())


def updateLabel(label, text):
    label.setText(text)
    QtWidgets.QApplication.processEvents()


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    mainW = Aucom()
    mainW.show()
    sys.exit(app.exec_())
