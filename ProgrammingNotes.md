## Bit of Precision Issue? ##

the step size of the uint16 image is wrong. It is half of what it should be (640 instead of 1280). Setting it manually keeps the program running.

However, the flag value for bad return is 1023 (2<sup>10</sup> - 1) instead of 2047 (2<sup>11</sup> -1). It seems to me that this might also have something to do with the bad step size.

The output looks correct, but it seems like the depth, if missing a bit, could be twice as accurate.



Ideas:

I could look at the uint16 in dat2ros and see if the flag value there is the correct 2047. This would tell me where the error was. If this was correct, the error would be the bridge between dat2ros and gaze-tracker-cmu.

If it comes straight off the f.read() like this, the issue might be some endian thing? Or maybe the data is just bad? Could look at the kinectrecorder.cpp file for clues here. Looked once, it seems the recorder is not the culprit. Maybe the ofx driver itself?


## Launch File Incompatibility ##

the format from the raw file is now different from the raw kinect output. Therefore, my launch file is broken.

I can either:

1. not bother. We don't need live kinect data anymore for testing

2. add a new flag into the code that is set in the launch file. The two times where things are different, check the flag first. This is yucky because the idea behind the launch file is that if the input is correct, we don't care where it comes from. HOWEVER, it would be pretty easy to implement

3. do the proper conversion in dat2ros. The weird thing here is that I will have yet again another source of discretization error, since the converting function outputs a float and I will have to do an uint16 (mm) per pixel. Plus, converting the entire image is unneccessary if I only extract a cloud from the face detections.




## Implementation and Visuals ##

2. the viola jones algorithm isn't working as well as it should. Missing a surprising amount of faces. Make me wonder if we shouldn't do LK tracking after all. Tried setting image\_scale to 1, didn't seem to really help. Perhaps the frontal\_alt thing would work? UPDATE: Going to statically set the face boxes for now, need to add mouse functionality. This also solves the problem if faces drop out of the frame (although some faces will move outside of the static frame, so tracking would still theoretically be better)

3. using the different cascades, some boxes appear within boxes, or boxes collide (is this true? don't know if I have actually witnessed this, though it is definitely possible)

4. the depth data is actually pretty terrible. Perhaps some really simple form of icp would work? All I am getting it a super rough half-ellipsoid. UPDATE: Chin tracking?

5. dat2ros doesnt shut down cleanly when it hits the end of file

6. for some reason, I lose keyboard control of dat2ros when I run gaze. Should I just not show the gaze window? UPDATE: Did not have this problem on the laptop.

7. viola jones is slow, not really "real-time" unless I size down the image

8. need to more tightly integrate the code that reads the csv and normal output files to make the dataset file.

9. Since the subversion is just the gaze-tracking-cmu ros node, the dataset creation scripts and the dat2ros node are not in it. make a new subversion? Move stuff around? Make a gaze tracking stack (like pi\_vision?)