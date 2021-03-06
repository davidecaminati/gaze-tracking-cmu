#!/usr/bin/env python
import roslib; roslib.load_manifest('gaze-tracking-cmu')
import rospy
from sensor_msgs.msg import PointCloud2, PointField, Image, RegionOfInterest
from visualization_msgs.msg import MarkerArray, Marker
from geometry_msgs.msg import Point
import numpy as np
from point_cloud import read_points, create_cloud, create_cloud_xyz32
from scipy.linalg import eig, norm
import cv
from cv_bridge import CvBridge, CvBridgeError
import time
import sys
from lk import lk
from dxySegment import dxySegment

class Gaze:
    def __init__(self, node_name):
        rospy.init_node(node_name)
        
        rospy.on_shutdown(self.cleanup)
    
        self.node_name = node_name
        self.input_rgb_image = "input_rgb_image"
        self.input_depth_image = "input_depth_image"
        
        self.prevDepth = None
        
        self.pubFaceCloud = rospy.Publisher('gaze_cloud', PointCloud2)
                
        """ Initialize a number of global variables """
        self.image = None
        self.image_size = None
        self.depth_image = None
        self.grey = None
        self.small_image = None
        self.prev = None
        self.prev_img = None
        self.show_text = True
        self.prevFrameNum = 1
        
        self.mask = None

        """ Create the display window """
        self.cv_window_name = self.node_name
        cv.NamedWindow(self.cv_window_name, cv.CV_NORMAL)
        cv.ResizeWindow(self.cv_window_name, 640, 480)
        
        cv.NamedWindow('face box')
        
        """ Create the cv_bridge object """
        self.bridge = CvBridge()   
        
        """ Set a call back on mouse clicks on the image window """
        cv.SetMouseCallback (self.node_name, self.on_mouse_click, None)  
        
        """ Subscribe to the raw camera image topic and set the image processing callback """
        self.image_sub = rospy.Subscriber(self.input_rgb_image, Image, self.image_callback)
        self.depth_sub = rospy.Subscriber(self.input_depth_image, Image, self.depth_callback)
        
        #rospy.Subscriber("/camera/depth/image", Image, callback, 
        #                 queue_size=1, callback_args=(pubFaceCloud,pubFaceNormals)) 
        #rospy.Subscriber("/roi", RegionOfInterest, callback, 
        #                 queue_size=1, callback_args=(pubFaceCloud,pubFaceNormals)) 
    
        """ Set up the face detection parameters """
        self.cascade_frontal_alt = rospy.get_param("~cascade_frontal_alt", "")
        self.cascade_frontal_alt2 = rospy.get_param("~cascade_frontal_alt2", "")
        self.cascade_profile = rospy.get_param("~cascade_profile", "")
        
        self.cascade_frontal_alt = cv.Load(self.cascade_frontal_alt)
        self.cascade_frontal_alt2 = cv.Load(self.cascade_frontal_alt2)
        self.cascade_profile = cv.Load(self.cascade_profile)
        
        self.camera_frame_id = "kinect_depth_optical_frame"
        
        self.depthFrameNum = 1
        
        self.drag_start = None
        self.selections = []
        
        # viola jones parameters
        self.min_size = (20, 20)
        self.image_scale = 2
        self.haar_scale = 1.5
        self.min_neighbors = 1
        self.haar_flags = cv.CV_HAAR_DO_CANNY_PRUNING
        
        self.seeds = None
        
        self.cps = 0 # Cycles per second = number of processing loops per second.
        self.cps_values = list()
        self.cps_n_values = 20
        
        self.featureFile = open('/home/ben/Desktop/features/batch9_features.dat','w')
        self.clusters = [5,4,4,3,3,5,4,3,3][9-1]
        
                        
        """ Wait until the image topics are ready before starting """
        rospy.wait_for_message(self.input_rgb_image, Image)
        rospy.wait_for_message(self.input_depth_image, Image)
            
        rospy.loginfo("Starting " + self.node_name)
            

    def detect_faces(self, cv_image):
        if self.grey is None:
            """ Allocate temporary images """      
            self.grey = cv.CreateImage(self.image_size, 8, 1)
            
        if self.small_image is None:
            self.small_image = cv.CreateImage((cv.Round(self.image_size[0] / self.image_scale),
                       cv.Round(self.image_size[1] / self.image_scale)), 8, 1)

        """ Convert color input image to grayscale """
        cv.CvtColor(cv_image, self.grey, cv.CV_BGR2GRAY)
        
        """ Equalize the histogram to reduce lighting effects. """
        cv.EqualizeHist(self.grey, self.grey)

        """ Scale input image for faster processing """
        cv.Resize(self.grey, self.small_image, cv.CV_INTER_LINEAR)

        """ First check one of the frontal templates """
        frontal_faces = cv.HaarDetectObjects(self.small_image, self.cascade_frontal_alt, cv.CreateMemStorage(0),
                                             self.haar_scale, self.min_neighbors, self.haar_flags, self.min_size)
                                         
        """ Now check the profile template """
        profile_faces = cv.HaarDetectObjects(self.small_image, self.cascade_profile, cv.CreateMemStorage(0),
                                             self.haar_scale, self.min_neighbors, self.haar_flags, self.min_size)

        """ Lastly, check a different frontal profile """
        #faces = cv.HaarDetectObjects(self.small_image, self.cascade_frontal_alt2, cv.CreateMemStorage(0),
        #                                 self.haar_scale, self.min_neighbors, self.haar_flags, self.min_size)
        #profile_faces.extend(faces)
            
        '''if not frontal_faces and not profile_faces:
            if self.show_text:
                text_font = cv.InitFont(cv.CV_FONT_VECTOR0, 3, 2, 0, 3)
                cv.PutText(self.marker_image, "NO FACES!", (50, int(self.image_size[1] * 0.9)), text_font, cv.RGB(255, 255, 0))'''
             
        faces_boxes = []   
        for ((x, y, w, h), n) in frontal_faces + profile_faces:
            """ The input to cv.HaarDetectObjects was resized, so scale the 
                bounding box of each face and convert it to two CvPoints """
            pt1 = (int(x * self.image_scale), int(y * self.image_scale))
            pt2 = (int((x + w) * self.image_scale), int((y + h) * self.image_scale))
                
            face_box = (pt1[0], pt1[1], pt2[0], pt2[1])
            faces_boxes.append(face_box)
        return faces_boxes

    def process_faces(self, boxes):     
        if not self.depth_image: 
            print 'whoops! no depth image!'
            return
          
        skip = 1
        xyz_all = []
        
        idNum = 1
        #f = open("output.dat","w")
        boxNum = 1
        prevV = None
        for (x1,y1,x2,y2) in boxes:
            x1, y1, x2, y2 = cv.Round(x1), cv.Round(y1), cv.Round(x2), cv.Round(y2)
            for xpad, ypad, ypad2 in zip([10,10],[40,40],[40,0]):

                if ypad2 == 0:
                    colorFlag = 2
                else:
                    colorFlag = 1

                u,v = np.mgrid[y1-ypad:y2+ypad2:skip,x1-xpad:x2+xpad:skip]
                u,v = u.flatten(), v.flatten()
                d = np.asarray(self.depth_image[y1-ypad:y2+ypad2,x1-xpad:x2+xpad])
                d = d[::skip,::skip]
                d = d.flatten()
                
                u = u[np.isfinite(d)]
                v = v[np.isfinite(d)]
                d = d[np.isfinite(d)]
                
                ### only if from dat, bad value should actually be 2047
                u = u[d!=0]
                v = v[d!=0]
                d = d[d!=0]
                
                #u = u[d < alpha*median]
                #v = v[d < alpha*median] 
                #d = d[d < alpha*median]
                
                xyz = self.makeCloud_correct(u,v,d)
                
                '''median = sorted(xyz[:,2])[len(d)//2]
                alpha = 1.2
                xyz = xyz[xyz[:,2] < alpha*median,:]'''
                
                xyz_all.extend(xyz)
                
                try:
                    n = len(xyz)
                    mu = np.sum(xyz, axis=0)/n
                    xyz_norm = xyz - mu
                    cov = np.dot(xyz_norm.T, xyz_norm)/n
                    e, v = eig(cov)
                    
                    #print v[2]
                    
                    if v[2][2] > 0: v[2] = -v[2]
                    
                    # publish marker here
                    if colorFlag == 1:
                        m = self.makeMarker(mu, v[2], idNum=idNum, color=(1,0,0))
                        print '%d %f %f %f' % (boxNum, v[2][0], v[2][1], v[2][2]),
                    else:
                        m = self.makeMarker(mu, v[2], idNum=idNum, color=(0,1,0))
                        print '%f %f %f ' % (v[2][0], v[2][1], v[2][2])
                    idNum += 1
                    self.pubFaceNormals.publish(m)
                except:
                    pass
            boxNum += 1
          
        # getting rid of bad markers in rviz by sending them away  
        for blah in range(idNum,25):
            m = self.makeMarker([-10,-10,-10], [1,1,1], idNum=idNum, color=(1,1,1))
            idNum += 1
            self.pubFaceNormals.publish(m)

        pc = PointCloud2()
        pc.header.frame_id = "/camera_rgb_optical_frame"
        pc.header.stamp = rospy.Time()
        pc = create_cloud_xyz32(pc.header, xyz_all)
        self.pubFaceCloud.publish(pc)
        
    def display_markers(self):
        # If the user is selecting a region with the mouse, display the corresponding rectangle for feedback.
        if self.drag_start and self.is_rect_nonzero(self.selection):
            x,y,w,h = self.selection
            cv.Rectangle(self.display_image, (x, y), (x + w, y + h), (0, 255, 255), 2)
            self.selected_point = None
        
    def is_rect_nonzero(self, r):
        # First assume a simple CvRect type
        try:
            (_,_,w,h) = r
            return (w > 0) and (h > 0)
        except:
            # Otherwise, assume a CvBox2D type
            ((_,_),(w,h),a) = r
            return (w > 0) and (h > 0)         
        
        
    def on_mouse_click(self, event, x, y, flags, param):
        """ We will usually use the mouse to select points to track or to draw a rectangle
            around a region of interest. """
        if not self.image:
            return
        
        if self.image.origin:
            y = self.image.height - y
            
        if event == cv.CV_EVENT_LBUTTONDOWN and not self.drag_start:
            self.detect_box = None
            self.selected_point = (x, y)
            self.drag_start = (x, y)
            
        if event == cv.CV_EVENT_LBUTTONUP:
            self.drag_start = None
            x, y, w, h = self.selection
            if w > 0 and h > 0:
                x1, y1, x2, y2 = x, y, x+w, y+h   
                self.selections.append((x1, y1, x2, y2))
            
        if self.drag_start:
            xmin = max(0, min(x, self.drag_start[0]))
            ymin = max(0, min(y, self.drag_start[1]))
            xmax = min(self.image.width, max(x, self.drag_start[0]))
            ymax = min(self.image.height, max(y, self.drag_start[1]))
            self.selection = (xmin, ymin, xmax - xmin, ymax - ymin)
            
    def depth_callback(self, data):
        depth_image = self.convert_depth_image(data)
            
        if not self.depth_image:
            (cols, rows) = cv.GetSize(depth_image)
            self.depth_image = cv.CreateMat(rows, cols, cv.CV_16UC1) # cv.CV_32FC1
            
        cv.Copy(depth_image, self.depth_image)

    def image_callback(self, data):       
        start = time.time()
    
        """ Convert the raw image to OpenCV format using the convert_image() helper function """
        cv_image = self.convert_image(data)
          
        """ Create a few images we will use for display """
        if not self.image:
            self.image_size = cv.GetSize(cv_image)
            self.image = cv.CreateImage(self.image_size, 8, 3)
            self.display_image = cv.CreateImage(self.image_size, 8, 3)


        """ Copy the current frame to the global image in case we need it elsewhere"""
        cv.Copy(cv_image, self.image)
        
        #cv.Copy(cv_image, self.display_image)
        
        #faces = self.detect_faces(cv_image)
        #faces = self.selections #((148,140,216,224),(424,166,500,238),(276,150,350,234))
        
        
        
        if not self.depth_image: 
            print 'no depth image'
            return
            
        
        if np.all(np.asarray(self.depth_image) == self.prevDepth):
            return
            
        self.prevDepth = np.asarray(self.depth_image).copy()
        
        np_image = np.asarray(cv_image).copy()
        np_depth = np.asarray(self.depth_image).copy()
        depth_im = cv.fromarray(np_depth)
        #np_depth[np_depth > 2000] = 0
    
        faces = []
        
        if self.seeds is None:
            faces, centroids = dxySegment(np_depth, nClusters=self.clusters, skip=1)
            self.seeds = centroids
        else:
            faces, centroids = dxySegment(np_depth, seeds=self.seeds, skip=1)
            self.seeds = centroids
            
        for faceNum, face in enumerate(sorted(faces)):
            # step 1: extract depth image according to face box
            x1, y1, x2, y2 = face
            #if x1 > x2: x2, x1 = x1, x2
            #if y1 > y2: y2, y1 = y1, y2
            print x1, x2, y1, y2
            face_cropped = depth_im[y1:y2,x1:x2]
            f_cropped_rgb = cv_image[y1:y2,x1:x2]
            cv.ShowImage('face box', f_cropped_rgb)
            
            # step 2: resize depth image into 20x20
            face_small = cv.CreateMat(20, 20, cv.CV_16UC1)
            cv.Resize(face_cropped, face_small)
            
            # step 3: output feature vector as flattened (400-dimensional) array
            self.featureFile.write(str(faceNum+1) + '\t' + '\t'.join([str(x) for x in np.asarray(face_small).flatten()]) + '\n')
            print str(faceNum+1) + '\t' + '\t'.join([str(x) for x in np.asarray(face_small).flatten()[:7]])
        
        """ Process the image to detect and track objects or features """
        '''if self.depthFrameNum == self.prevFrameNum: 
            pass
        else:
            curr = np.asarray(self.depth_image)
            
            ### TRACKING WITH LUCAS-KANADE
            tracked_faces = []
            
            if self.prev is not None:
                for facebox in faces:
                    u, v = lk(curr,self.prev,facebox)
                    print 'tracking...', u, v
                    tracked_faces.append((facebox[0]+u,
                                          facebox[1]+v,
                                          facebox[2]+u,
                                          facebox[3]+v))
                    
                faces = tracked_faces
                self.selections = faces
            self.prev = curr.copy()
            self.prev_img = np.asarray(cv_image)
            self.prevFrameNum = self.depthFrameNum
            self.process_faces(faces)'''
            

        #self.mask = cv.CreateImage(self.image_size, 8, 1)  
        #self.display_image = cv.CreateImage(self.image_size, 8, 3) 
        #cv.Set(self.display_image,0)         
        #cv.CmpS(cv.fromarray(np.asarray(self.depth_image).astype(np.uint8)), 0, self.mask, cv.CV_CMP_NE)
        #cv.CmpS(self.depth_image, 0, self.mask, cv.CV_CMP_NE)
        #cv.Copy(cv_image, self.display_image, mask=self.mask)
        
        #np_image[np_depth == 0] = 0
        self.display_image = cv.fromarray(np_image)
            
        for pl, (x,y,x2,y2) in enumerate(sorted(faces)):
            cv.Rectangle(self.display_image, (cv.Round(x), cv.Round(y)),
                                             (cv.Round(x2), cv.Round(y2)), 
                                             cv.RGB(255, pl*50, 0), 2, 8, 0)
        
        """ Handle keyboard events """
        self.keystroke = cv.WaitKey(2)
            
        end = time.time()
        duration = end - start
        fps = int(1.0 / duration)
        self.cps_values.append(fps)
        if len(self.cps_values) > self.cps_n_values:
            self.cps_values.pop(0)
        self.cps = int(sum(self.cps_values) / len(self.cps_values))
        
        if self.show_text:
            text_font = cv.InitFont(cv.CV_FONT_VECTOR0, 1, 1, 0, 2, 8)
            """ Print cycles per second (CPS) and resolution (RES) at top of the image """
            cv.PutText(self.display_image, "FPS: " + str(self.cps), (10, int(self.image_size[1] * 0.1)), text_font, cv.RGB(255, 255, 0))
            #cv.PutText(self.display_image, "RES: " + str(self.image_size[0]) + "X" + str(self.image_size[1]), (int(self.image_size[0] * 0.6), int(self.image_size[1] * 0.1)), text_font, cv.RGB(255, 255, 0))
            
        #self.display_markers()

        # Now display the image.
        cv.ShowImage(self.node_name, self.display_image)
        
        """ Process any keyboard commands """
        if 32 <= self.keystroke and self.keystroke < 128:
            cc = chr(self.keystroke).lower()
            if cc == 't':
                self.show_text = not self.show_text
            elif cc == 'q':
                """ user has press the q key, so exit """
                rospy.signal_shutdown("User hit q key to quit.")      

    def convert_image(self, ros_image):
        try:
            cv_image = self.bridge.imgmsg_to_cv(ros_image, "bgr8")
            return cv_image
        except CvBridgeError, e:
          print e
          
    def convert_depth_image(self, ros_image):
        try:
            
            #ros_image.step = 1280 # weird bug here -- only needed for dat?
            depth_image = self.bridge.imgmsg_to_cv(ros_image, "16UC1") #"32FC1"

            return depth_image
    
        except CvBridgeError, e:
            print e    
 
    def makeCloud_correct(self, u, v, d): # for depth values, from pi_vision
        # only if from dat
        #d = 1000.0 * .1236 * np.tan((d / 2842.5) + 1.1863) - 0.0370
        
        const = .001/575.8157348632812
        
        xp = d*const*(v-314.5)
        yp = d*const*(u-235.5)
        zp = d*0.001
        
        return np.vstack((xp,yp,zp)).T
            
    def makeCloud(self, u, v, d): # for depth values, from pi_vision
        xyz = []
        C = np.vstack((u.flatten(), v.flatten(), d.flatten()))  

        for i in range(C.shape[1]):
            
            y, x, z = C[0,i], C[1,i], C[2,i]
            
            zp = z #1.0 / (z * -0.0030711016 + 3.3309495161)
            #print z, zp
            
            #550,.1 or 0,600 (saw 0,603.3)
            xp = (zp-.0) * 1.094 * (x - 640 / 2.0) / float(603.3) 
            yp = (zp-.0) * 1.094 * (y - 480 / 2.0) / float(603.3) #550
            
            if not np.isnan(xp) and not np.isnan(yp) and not np.isnan(zp):
                xyz.append((xp,yp,zp))
        return xyz
                    

    
    def makeMarker(self, pos, vec, idNum=1, color=(1,0,0)):
        m = Marker()
        m.id = idNum
        m.ns = "test"
        m.header.frame_id = "/camera_rgb_optical_frame"
        m.type = Marker.ARROW
        m.action = Marker.ADD
        
        markerPt1 = Point()
        markerPt2 = Point()
        markerPt1.x = pos[0];
        markerPt1.y = pos[1];
        markerPt1.z = pos[2];
        markerPt2.x = markerPt1.x + vec[0];
        markerPt2.y = markerPt1.y + vec[1];
        markerPt2.z = markerPt1.z + vec[2];
        
        m.points = [markerPt1, markerPt2]
        
        m.scale.x = .1;
        m.scale.y = .1;
        m.scale.z = .1;
        m.color.a = 1;
        m.color.r = color[0];
        m.color.g = color[1];
        m.color.b = color[2];
        #m.lifetime = rospy.Duration()
        return m
        
    def cleanup(self):
        print "Shutting down vision node."
        self.featureFile.close()
        cv.DestroyAllWindows()  
    
def main(args):
    """ Display a help message if appropriate """
    '''help_message =  "Hot keys: \n" \
          "\tq - quit the program\n" \
          "\tc - delete current features\n" \
          "\tt - toggle text captions on/off\n" \
          "\tf - toggle display of features on/off\n" \
          "\tn - toggle \"night\" mode on/off\n" \
          "\ta - toggle auto face tracking on/off\n"

    print help_message'''
    
    """ Fire up the Face Tracker node """
    g = Gaze("gaze")

    try:
      rospy.spin()
    except KeyboardInterrupt:
      print "Shutting down face tracker node."
      cv.DestroyAllWindows()

if __name__ == '__main__':
    main(sys.argv)
