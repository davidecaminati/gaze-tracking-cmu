# Introduction #

In the Kinect x is horizontal, y is vertical and z is depth (an optical frame of reference).

Here we outline our approach to estimating gaze-direction labels by interpolating participant locations from our depth data, classifying their vertical tilt, then transforming to their horizontal (x-z) coordinate system to calculate their cone of attention.


# Details #

We propose three possible strategies for estimating gaze direction, 1) Transform world to subject coordinate system and calculate angle thresholds for gaze direction classifications, 2) Calculate cone of attention given subject nose-normal and ray cast to best object-of-attention classification, 3) Take a machine learning approach, matching human labeled gaze-directions to the feature vector of x,y,z nose normals and participant location.

STRATEGY 1: Angle Thresholds


Estimate t, t' and t'', where t and t' are constant for all participants and t'' can be calculated given the subject's location:

```
Tilt labels:                      

   /\                            Yaw labels:
    |   UP                   
    |
    | -t                                t''
    |                        ROBOT      |    WINDOW
    |   MIDDLE                <---------------------->
    | 
    | -t'
    | 
    |   DOWN
   \/
```

Psuedocode 1:
  1. Use tilt angle to segment {up, middle, down} -- if up: VENT, if down: FLOOR, if middle: continue
  1. Use yaw angle and position to estimate intra-participant gaze {true, false} -- if true: EACHOTHER, if false: continue
  1. Use yaw angle to segment {robot, window} --if robot: ROBOT, if window: WINDOW

STRATEGY 2: Attentional Cone

Psuedocode 2:
  1. Detect subject location
  1. Estimate cone of attention for each subject, given nose normal
  1. Use ray casting to classify to best direction category

STRATEGY 3: Data-driven Approach

Use machine learning algorithms (e.g. SVM) to find the best feature-based classification scheme. We have 34 participants labeled with 5-possible gaze-locations for seventeen seconds each at half-second intervals. All occur for a particular robot tour guide location and script.  As it is a relatively small dataset we intend to use 10-fold cross validation.  The feature vectors for each participant at each timestep will be the x, y, z Nose-normal vectors and subject location.