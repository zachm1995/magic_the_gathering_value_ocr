# Imports
from cv2 import cv2
import pdb
import numpy as np
import pytesseract as pt
import json
from fuzzywuzzy import fuzz
from fuzzywuzzy import process

pt.pytesseract.tesseract_cmd= "/usr/local/Cellar/tesseract/4.1.1/bin/tesseract"

def empty():
    pass

def build_card_list():
    with open('data.json', 'r') as json_file:
        data = json.load(json_file)
    cardList = []
    for key, value in data.items():
        for card in value['cards']:
            cardList.append(card)
    return cardList

# Returns the card dictionary if it fuzzy matches key in database
def get_card_by_name(cardList, name):
    if len(list(filter(lambda card: fuzz.token_sort_ratio(name, card["name"]) > 80, cardList))) > 0:
        return list(filter(lambda card: fuzz.token_sort_ratio(name, card["name"]) > 80, cardList))[0]
    return None
    
def generate_trackbars():
    cv2.namedWindow("Image settings")
    cv2.resizeWindow("Image settings", 640, 300)
    cv2.createTrackbar("Hue Min", "Image settings", 0, 179, empty)

def get_contours(originalImg, img):
    maxContour = np.array([])
    maxArea = 0
    contours, heirarchy = cv2.findContours(img, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 5000:
            perimeter = cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, .02 * perimeter, True)
            if area > maxArea and len(approx) == 4:
                maxContour = approx
                maxArea = area
                cv2.drawContours(contouredFrame, maxContour, -1, (255, 0, 0), 30)
    return maxContour


def process_image(img):
    greyed = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blured = cv2.GaussianBlur(greyed, (5,5), 0)
    edged = cv2.Canny(blured, 100, 100)
    # kernel = np.ones((5, 5))
    # dialated = cv2.dilate(edged, kernel, iterations=2)
    # threshold = cv2.erode(dialated, kernel, iterations=1)
    return edged

def reorder_points(documentEdge):
    points = documentEdge.reshape((4, 2))
    newPoints = np.zeros((4, 1, 2), np.int32)

    # Sums the x and y for each coordinate and adds to sum array
    sum = points.sum(1)
    newPoints[0] = points[np.argmin(sum)]
    newPoints[3] = points[np.argmax(sum)]

    diff = np.diff(points, axis=1)
    newPoints[1] = points[np.argmin(diff)]
    newPoints[2] = points[np.argmax(diff)]

    return newPoints

def warp_image(originalImg, img, documentEdge):
    width, height = img.shape
    if len(documentEdge) == 4:
        x,y,w,h = cv2.boundingRect(documentEdge)
        card = originalImg[y:y+h, x:x+w]
        cv2.imshow("Card", card)
        documentEdge = reorder_points(documentEdge)

        pts1 = np.array(documentEdge)
        pts2 = np.array([[0, 0], [w, 0], [0, h], [w, h]])
        matrix = cv2.getPerspectiveTransform(np.float32(pts1), np.float32(pts2))
        warpedImage = cv2.warpPerspective(originalImg, matrix, (w, h))
        return warpedImage
    else:
        return img

def card_title_ocr(img):
    cardTitleImage = img[30:80, 30:300]
    return pt.image_to_string(cardTitleImage)

# Init webcam connection
cv2.namedWindow("Webcam")
camera = cv2.VideoCapture(1)
retVal, frame = camera.read()
camera.set(3, 1080)
camera.set(4, 1920)

# Get card list from data
cardList = build_card_list()

# Read camera and display to screen until user presses 'q' key
while camera.isOpened():
    # Read frame from webcam stream
    retVal, frame = camera.read()
    frame = cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)

    # Process the frame
    processedFrame = process_image(frame)

    # Make copy of frame to draw contour
    contouredFrame = processedFrame.copy()

    # Get the bounding box of the card
    documentEdge = get_contours(frame, contouredFrame)

    # Use warped translate 
    warpedFrame = warp_image(frame, contouredFrame, documentEdge)

    # Get name of card from ocr
    cardTitleOCR = card_title_ocr(warpedFrame)
    card = get_card_by_name(cardList, cardTitleOCR)

    # Adds card name and value to frame output
    cv2.putText(warpedFrame, card["name"], (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0))
    cv2.putText(warpedFrame, card["value"], (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0))
    
    # Show frame in window
    cv2.imshow("Webcam", warpedFrame)

    # If the card has any value, pause the feed and ask to save
    if float(card["value"][1:]) > 0:
        cv2.waitKey(-1)
        cv2.putText(warpedFrame, "Press 's' to save", (100, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0))

    # Wait for user to press 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break
