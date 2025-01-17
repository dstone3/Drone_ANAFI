import time, sys
import ps_drone                                    # Import PS-Drone-API
import numpy as np
import cv2
import math
from pyimagesearch.centroidtracker import CentroidTracker
import os
import pickle

class ourDrone:

    def __init__(self):
        
        self.prototxt = "deploy.prototxt"
        self.model = "res10_300x300_ssd_iter_140000.caffemodel"
        self.ct = CentroidTracker()
        self.net = cv2.dnn.readNetFromCaffe(self.prototxt, self.model)
        self.classes = ["background", "aeroplane", "bicycle", "bird", "boat",
	           "bottle", "bus", "car", "cat", "chair", "cow", "diningtable",
	           "dog", "horse", "motorbike", "person", "pottedplant", "sheep",
	           "sofa", "train", "tvmonitor"]
        self.COLORS = np.random.uniform(0,255,size=(len(self.classes), 3))

        self.net2 = cv2.dnn.readNetFromCaffe("net.prototxt.txt", "netMode.caffemodel")

        self.face_cascade = cv2.CascadeClassifier('frontalface.xml')
        self.protoPath = os.path.sep.join(["face_detection_model", "deploy.prototxt"])
        self.modelPath = os.path.sep.join(["face_detection_model",
	"res10_300x300_ssd_iter_140000.caffemodel"])
        self.detector = cv2.dnn.readNetFromCaffe(self.protoPath, self.modelPath)
        self.embedder = cv2.dnn.readNetFromTorch("openface_nn4.small2.v1.t7")
        self.recognizer = pickle.loads(open("output/recognizer.pickle", "rb").read())
        self.le = pickle.loads(open("output/le.pickle", "rb").read())
        self.drone = ps_drone.Drone()# Initialize drone class
        self.drone.startup() # Connects to drone and starts subprocesses
        self.drone.reset() # Sets drone's status to good
        while (self.drone.getBattery()[0]==-1): time.sleep(0.1) # Wait until drone has done its reset
        print "Battery: "+str(self.drone.getBattery()[0])+"% "+str(self.drone.getBattery()[1]) # Battery-status
        self.drone.useDemoMode(True) # Set 15 basic dataset/sec
        self.takeOff()

        ##### Variables for States #####
        self.object_flag = False
        self.cnt = 0
        self.x_int = 0
        self.y_int = 0
        self.w_int = 0
        self.x_old = 0
        self.y_old = 0
        self.w_old = 0

        ##### Mainprogram begin #####
        self.drone.setConfigAllID() # Go to multiconfiguration-mode
        self.drone.hdVideo()
        self.drone.frontCam()  # Choose ground view, alternative is frontCam()
        CDC = self.drone.ConfigDataCount
        while CDC==self.drone.ConfigDataCount or self.drone.getKey(): time.sleep(0.001) # Wait until it is done (after resync)

        self.IMC = None
        self.stop = False
        self.ground= False

        self.imgW = 0
        self.imgH = 0
        self.objBox = (0,0,0,0) # (x,y,x+w, y+h)
        print("Drone initialization complete")

    def startVideo(self):
        self.drone.startVideo()
        #drone.showVideo()
        
        IMC = self.drone.VideoImageCount # Number of encoded videoframes
        time.sleep(5)
        print("Video stream started")

    def trackColor(self, frame):
        
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV) 

        lower_red = np.array([30, 100, 20]) 
        upper_red = np.array([50, 255, 255]) 
  
        mask = cv2.inRange(hsv, lower_red, upper_red) 
        res = cv2.bitwise_and(frame,frame, mask= mask) 
        #cv2.imshow('mask',cv2.resize(mask,(800,800) )) 
        #cv2.imshow('res',res)
    
        contours, hier = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        if len(contours) != 0:
           cont = max(contours, key = cv2.contourArea)
    
           (x,y,w,h) = cv2.boundingRect(cont)

           self.objBox = (x,y,w+x,h+y)
           cv2.rectangle(frame, (x,y),(x+w,y+h),(255,0,0),1)

           self.imgW = 600
           self.imgH = 600
        
        cv2.imshow('frame', cv2.resize(frame, (600,600)))
        key = cv2.waitKey(1) & 0xFF
    
    def findAdam(self, frame):
        (h,w) = frame.shape[:2]
        
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) 

	# Detects faces of different sizes in the input image 
	faces = self.face_cascade.detectMultiScale(gray, 1.3, 5) 
        
        
	# loop over the detections
	for (x,y,w,h) in faces:
	    
	    face = frame[y:y+h, x:x+w]
	    faceBlob = cv2.dnn.blobFromImage(face, 1.0 / 255,
				             (96, 96), (0, 0, 0), swapRB=True, crop=False)
	    self.embedder.setInput(faceBlob)
	    vec = self.embedder.forward()
                
			# perform classification to recognize the face
	    preds = self.recognizer.predict_proba(vec)[0]
	    j = np.argmax(preds)
	    proba = preds[j]
	    name = self.le.classes_[j]
                
	    # draw the bounding box of the face along with the
	    # associated probability
            #print("Name = ", name)
            if(name == "Adam Sandler"):
                self.object_flag = True
                self.objBox = (x, y, x+w, y+h)
                #print(self.objBox)
            else:
                self.object_flag = False
                
            text = "{}: {:.2f}%".format(name, proba * 100)
		
	    cv2.rectangle(frame, (x, y), (x+w, y+h),
			  (0, 0, 255), 2)
	    cv2.putText(frame, text, (x, y-5),
		        cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 255), 2)
                

	

	# show the output frame
	frame= cv2.resize(frame, (600,600))
	cv2.imshow("Frame", frame)
	key = cv2.waitKey(2)



    def trackPerson(self, img):
        frame = img
        
        # if the frame dimensions are None, grab them
        (H,W) = frame.shape[:2]
        self.imgW = W
        self.imgH = H
	# construct a blob from the frame, pass it through the network,
	# obtain our output predictions, and initialize the list of
	# bounding box rectangles
        blob = cv2.dnn.blobFromImage(frame, 1.0, (W, H),(104.0, 177.0, 123.0))
        
        self.net.setInput(blob)
        detections = self.net.forward()
        rects = []
        
        
        # loop over the detections
        for i in range(0, detections.shape[2]):
	    # filter out weak detections by ensuring the predicted
	    # probability is greater than a minimum threshold
            if detections[0, 0, i, 2] > .7:
	        # compute the (x, y)-coordinates of the bounding box for
	        # the object, then update the bounding box rectangles list
                box = detections[0, 0, i, 3:7] * np.array([W, H, W, H])
                if i == 0: # only first detection
                    self.objBox = box
                rects.append(box.astype("int"))
                            
	        # draw a bounding box surrounding the object so we can
	        # visualize it
                (startX, startY, endX, endY) = box.astype("int")
                cv2.rectangle(frame, (startX, startY), (endX, endY),
			(0, 255, 0), 2)

	# update our centroid tracker using the computed set of bounding
	# box rectangles
        objects = self.ct.update(rects)
        
	# loop over the tracked objects
        for (objectID, centroid) in objects.items():
		# draw both the ID of the object and the centroid of the
		# object on the output frame
            text = "ID {}".format(objectID)
            cv2.putText(frame, text, (centroid[0] - 10, centroid[1] - 10),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
            cv2.circle(frame, (centroid[0], centroid[1]), 4, (0, 255, 0), -1)

        cv2.imshow('frame', cv2.resize(frame, (600,600)))

    	# show the output frame
        #cv2.imshow("Frame", frame)
        key = cv2.waitKey(1) & 0xFF

	

    def findObject(self, image):

        (h,w) = image.shape[:2]
        self.imgW = w
        self.imgH = h
        
        blob = cv2.dnn.blobFromImage(cv2.resize(image, (300, 300)), 0.007843, (300, 300), 127.5)

        # pass the blob through the network and obtain the detections and
        self.net2.setInput(blob)
        detections = self.net2.forward()
    
        for i in np.arange(0, detections.shape[2]):
            # extract the confidence (i.e., probability) associated with the
	    # prediction
            confidence = detections[0, 0, i, 2]
        
	    # filter out weak detections by ensuring the `confidence` is
	    # greater than the minimum confidence
            if confidence > .6:
                idx = int(detections[0, 0, i, 1])
                box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
                (startX, startY, endX, endY) = box.astype("int")
                self.objBox = box
                
		# display the prediction
                label = "{}: {:.2f}%".format(self.classes[idx], confidence * 100)
                print("[INFO] {}".format(label))
                cv2.rectangle(image, (startX, startY), (endX, endY),
		    self.COLORS[idx], 2)
                y = startY - 15 if startY - 15 > 15 else startY + 15
                cv2.putText(image, label, (startX, y),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.COLORS[idx], 2)
        cv2.imshow("Frame", cv2.resize(image, (600,600)))
        key = cv2.waitKey(1) & 0xFF      

    def facialRec(self):
        ## recognize a face at a particular location
        print("test")

    def foundAlgorithm(self):
        ## Make movements based off on object's box location
        ## Idea is: Move slow and wait, keep object in view, algorithm is called when object has been detected in frame initially
        
        ## Algorithm assumes camera is ground camera
        ## Object should be corrected to be on the horizon but in some experimental x value
        
        ## Normalize coordinates, should range from 0-1
        objX = (self.objBox[2] - self.objBox[0]) / 2 / self.imgW
        objY = (self.objBox[3] - self.objBox[1]) / 2 / self.imgH
        ## Note, objY corresponds to a z-rotation, not a y-change
        
        pickupX = 50 / self.imgW ## experimental value, so needs to be changed
        pickupY = self.imgH / 2 ## horizon line

        #if pickupX == objX and pickupY == objY:
            ## descend to pick up object
        #else:
            ## move drone by objX - .5 and rotate drone by ?    

        time.sleep(2) ## give drone time to move


    def center(self):
        # Object Detection
        img = self.drone.VideoImage
        self.findAdam(img)

        # compute center and speeds
        x = ( self.objBox[0] + self.objBox[2] ) / 2.0
        y = ( self.objBox[1] + self.objBox[3] ) / 2.0
        x_error = x - 630
        y_error =  360 - y
        max_speed = 0.8
        x_speed = max_speed * x_error / 630.0
        y_speed = max_speed * y_error / 360.0

        # print  and move statement
        if (self.cnt == 1):
            if self.object_flag:
                print ("x: ", x_speed, "y: ", y_speed)
                #print ("x: ", self.objBox[0], "y: ", self.objBox[1])
                self.drone.move(x_speed, y_speed, 0, 0)
                time.sleep(0.1)
            else:
                print ("No object")
        elif (self.cnt >= 2):
            self.cnt = 0
        self.cnt = self.cnt + 1

    ## Main function to detect and navigate towards the object
    def testMove(self, xpos, ypos):
        # image detection
        img = self.drone.VideoImage
        self.findAdam(img)

        # compute center and speeds
        x = ( self.objBox[0] + self.objBox[2] ) / 2.0
        y = ( self.objBox[1] + self.objBox[3] ) / 2.0
        width = self.objBox[2] - self.objBox[0] 
        x_error = (x - 320) * (x - 320) * (x - 320)
        y_error = (180 - y) * (180 - y) * (180 - y)
        max_speed = 0.3
        x_speed = max_speed * x_error / 32768000.0
        y_speed = max_speed * y_error / 5832000.0
        x_speed = round(x_speed, 2)
        y_speed = round(y_speed, 2)

        # move drone
        if not self.object_flag:
            print "Searching!"
            self.drone.move(0,0,0,0.2)
        elif self.object_flag:
            print 'x: ', x_speed, 'y: ', y_speed
            self.drone.move(0, 0.04, y_speed, x_speed)
            if width >= 70:
                self.drone.stop()
                time.sleep(0.1)
                self.drone.move(0,0,-0.3,0)
                time.sleep(1.5)
                self.drone.move(0,0,0.3,0)
                time.sleep(1.5)
                self.drone.move(0,-0.2,0,0)
                time.sleep(1)
                sys.exit()

        # sleep
        time.sleep(0.02)

    ## test funciton for PID control
    def PIDMove(self):
        # image detection
        img = self.drone.VideoImage
        self.findAdam(img)

        # compute center and speeds
        x = ( self.objBox[0] + self.objBox[2] ) / 2.0
        y = ( self.objBox[1] + self.objBox[3] ) / 2.0
        width = self.objBox[2] - self.objBox[0] 
        x_error = x - 320
        y_error = 180 - y
        w_error = 70 - width
        max_speed = 0.3
        #x_speed = max_speed * x_error / 32768000.0
        #y_speed = max_speed * y_error / 5832000.0
        #x_speed = round(x_speed, 2)
        #y_speed = round(y_speed, 2)

        #proportional
        prop = 0.2
        xp = prop * x_error / 320.0
        yp = prop * y_error / 180.0
        wp = prop * w_error / 70.0

        #integral
        integ = 0.02
        self.x_int = self.x_int + x_error
        self.y_int = self.y_int + y_error
        self.w_int = self.w_int + w_error
        if (self.x_int >= 2000):
            x_int = 2000
        elif (self.x_int <= -2000):
            x_int = -2000
        if (self.y_int >= 1200):
            y_int = 1200
        elif (self.y_int <= -1200):
            y_int = -1200
        if (self.w_int >= 400):
            w_int = 400
        elif (self.w_int <= -400):
            w_int = -400
        xi = integ * self.x_int / 320.0
        yi = integ * self.y_int / 180.0
        wi = integ * self.w_int / 70.0

        #derivative
        der = 0.2
        xdc = x_error - self.x_old
        ydc = y_error - self.y_old
        wdc = w_error - self.w_old
        self.x_old = x_error
        self.y_olf = y_error
        self.w_old = w_error
        xd = der * xdc / 320.0
        yd = der * ydc / 180.0
        wd = der * wdc / 70.0

        #speed
        x_speed = xp + xi + xd
        y_speed = yp + yi + yd
        w_speed = wp + wi + wd

        # move drone
        if not self.object_flag:
            print "Searching!"
            self.drone.move(0,0,0,0.2)
        elif self.object_flag:
            print 'x: ', x_speed, 'y: ', y_speed
            self.drone.move(0, w_speed, y_speed, x_speed)
            if width >= 200:
                self.drone.stop()
                time.sleep(0.1)
                self.drone.move(0,0,-0.3,0)
                time.sleep(1.5)
                self.drone.move(0,0,0.3,0)
                time.sleep(1.5)
                self.drone.move(0,-0.2,0,0)
                time.sleep(1)
                sys.exit()

        # sleep
        time.sleep(0.02)



    def takeOff(self):
        #self.drone.getNDpackage(["demo"])
        time.sleep(0.5)
        self.drone.takeoff()
        while self.drone.NavData["demo"][0][2]: 
            time.sleep(0.1) # Wait until drone is completely flying




        
## main function
if __name__ == '__main__':
    stop = False

    thisDrone = ourDrone()
    thisDrone.startVideo()

    # centering flag
    center_flag = False
    test_flag = False
    pid_flag = False
    x_cnt = 0.0
    y_cnt = 0.0

    while not stop:
        #img = drone.videoImage
        #thisDrone.followPerson(img) ## call sample object detection method
        #thisDrone.moveAlgorithm() ## Move drone...drone should take off before this..?

        # key control
        key = thisDrone.drone.getKey()
        if key == "0":
            thisDrone.drone.hover()
            center_flag = False
            test_flag = False
            pid_flag = False
        elif key == "w":
            thisDrone.drone.moveForward()
        elif key == "s":
            thisDrone.drone.moveBackward()
        elif key == "a":
            thisDrone.drone.moveLeft()
        elif key == "d":
            thisDrone.drone.moveRight()
        elif key == "8":
            thisDrone.drone.moveUp()
        elif key == "2":
            thisDrone.drone.moveDown()
        elif key == "c":
            center_flag = True
        elif key == " ":
            sys.exit()
        elif key == "t":
            test_flag = True
        elif key == "j":
            x_cnt = x_cnt - 0.1
            print x_cnt
        elif key == "l":
            x_cnt = x_cnt + 0.1
            print x_cnt
        elif key == "i":
            y_cnt = y_cnt + 0.1
            print y_cnt
        elif key == "k":
            y_cnt = y_cnt - 0.1
            print y_cnt
        elif key == "p":
            pid_flag = True

        # test move from keyboard
        if test_flag:
            thisDrone.testMove(x_cnt, y_cnt)
            time.sleep(0.1)

        # pid control
        if pid_flag:
            thisDrone.PIDMove()

        # center drone on object
        if center_flag:
            thisDrone.center()

