import copy
import numpy as np
import cv2
from glob import glob
import os
import argparse
import json
import time
# video file processing setup
# from: https://stackoverflow.com/a/61927951
import argparse
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple
import torch

class FFProbeResult(NamedTuple):
    return_code: int
    json: str
    error: str


def ffprobe(file_path) -> FFProbeResult:
    command_array = ["ffprobe",
                     "-v", "quiet",
                     "-print_format", "json",
                     "-show_format",
                     "-show_streams",
                     file_path]
    result = subprocess.run(command_array, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
    return FFProbeResult(return_code=result.returncode,
                         json=result.stdout,
                         error=result.stderr)


# openpose setup
from src import model
from src import util
from src.body import Body
from src.hand import Hand

body_estimation = Body('model/body_pose_model.pth')
hand_estimation = Hand('model/hand_pose_model.pth')

def process_frame(frame, body=True, hands=True):
    canvas = copy.deepcopy(frame)
    with torch.no_grad():
        if body:
            candidate, subset = body_estimation(frame)
            #print('candidate',candidate)
            #print('subset', subset)
            canvas = util.draw_bodypose(canvas, candidate, subset)
        if hands:
            hands_list = util.handDetect(candidate, subset, frame)
            all_hand_peaks = []
            for x, y, w, is_left in hands_list:
                peaks = hand_estimation(frame[y:y+w, x:x+w, :])
                peaks[:, 0] = np.where(peaks[:, 0]==0, peaks[:, 0], peaks[:, 0]+x)
                peaks[:, 1] = np.where(peaks[:, 1]==0, peaks[:, 1], peaks[:, 1]+y)
                all_hand_peaks.append(peaks)
            canvas = util.draw_handpose(canvas, all_hand_peaks)
    return canvas

# writing video with ffmpeg because cv2 writer failed
# https://stackoverflow.com/questions/61036822/opencv-videowriter-produces-cant-find-starting-number-error
import ffmpeg

# open specified video
parser = argparse.ArgumentParser(
        description="Process a video annotating poses detected.")
parser.add_argument('--input', type=str, help='Video file location to process.')
parser.add_argument('--output', type=str, help='Video file location to process.')
parser.add_argument('--no_hands', action='store_true', help='No hand pose')
parser.add_argument('--no_body', action='store_true', help='No body pose')
args = parser.parse_args()
video_file = args.input
cap = cv2.VideoCapture(video_file)


class Writer():
    def __init__(self, output_file, input_fps, input_framesize, input_pix_fmt,
                 input_vcodec):
        if os.path.exists(output_file):
            os.remove(output_file)
        self.ff_proc = (
            ffmpeg
            .input('pipe:',
                   format='rawvideo',
                   pix_fmt="bgr24",
                   s='%sx%s'%(input_framesize[1],input_framesize[0]),
                   r=input_fps)
            .output(output_file, pix_fmt=input_pix_fmt, vcodec=input_vcodec)
            .overwrite_output()
            .run_async(pipe_stdin=True)
        )

    def __call__(self, frame):
        self.ff_proc.stdin.write(frame.tobytes())

    def close(self):
        self.ff_proc.stdin.close()
        self.ff_proc.wait()


#writer = None

t = time.time()

fourcc = cv2.VideoWriter_fourcc(*'mp4v')
outvideo = cv2.VideoWriter(args.output, fourcc, 60.0, (1280,  720))

while(cap.isOpened()):
    
    print('a', time.time() - t, 1/(time.time() - t))
    t = time.time()
    
    ret, frame = cap.read()
    if frame is None:
        break
    

    

    posed_frame = process_frame(frame, body=not args.no_body,
                                       hands=not args.no_hands)
    

    
    outvideo.write(posed_frame)
    
    #if writer is None:
    #    input_framesize = posed_frame.shape[:2]
    #    writer = Writer(output_file, input_fps, input_framesize, input_pix_fmt,
    #                    input_vcodec)
        


    cv2.imshow('frame', posed_frame)


    # write the frame
    #writer(posed_frame)
    

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
outvideo.release()
cap.release()
#writer.close()
cv2.destroyAllWindows()
