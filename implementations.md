## aam-opencv ##
  * http://code.google.com/p/aam-opencv/
  * training demo: http://www.youtube.com/watch?v=G0xtPWTfFlI
  * implementation of active appearance models (PCA faces) in opencv
  * getting opencv libs not found errors, project not actively maintained
  * requires training phase (as per youtube video)

## random forests ##
  * paper 1: http://www.vision.ee.ethz.ch/~gfanelli/pubs/dagm11.pdf
  * paper 2: http://www.vision.ee.ethz.ch/~gfanelli/pubs/cvpr11.pdf
  * code: http://www.vision.ee.ethz.ch/~gfanelli/head_pose/head_forest.html
  * link above includes giant 5+ GB dataset of kinect faces, annotated

## music face tracker ##
  * http://createdigitalmusic.com/2011/07/music-with-your-face-artist-kyle-mcdonald-talks-face-tracking-music-making-with-kinect/
  * http://web.mac.com/jsaragih/FaceTracker/FaceTracker.html
  * still waiting on 2nd email back from Jason...
  * from paper: J. Saragih, S. Lucey and J. Cohn, ``Deformable Model Fitting by Regularized Landmark Mean-Shifts", International Journal of Computer Vision (IJCV)
  * look promising, but might be overkill for our needs

## viola jones + camshift ##
  * implemented this for fun, didn't work so well, would shift off my face and attach to another object
  * also not 6dof

## http://www.ros.org/wiki/pi_face_tracker ##
  * uses good features to track in opencv and lucas-kanade (also uses kinect?)
  * does not do pose estimation, however, we can augment this one pretty easily
  * seems much more robust than viola jones (and faster!) (also in python&ros)

## www.opentl.org ##
  * http://www.youtube.com/watch?v=WIoGdhkfNVE&feature=related
  * requires training? yet to really look at this one in-depth

## ehci ##
  * http://code.google.com/p/ehci/
  * not really well-maintained...
  * seems pretty buggy/unstable
  * getting cmake compile errors, might not be worth the tmie to debug