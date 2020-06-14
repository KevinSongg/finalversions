import os
import sys
import argparse
import time
import signal
import math
import random
from unicodedata import bidirectional

# include the netbot src directory in sys.path so we can import modules from it.
robotpath = os.path.dirname(os.path.abspath(__file__))
srcpath = os.path.join(os.path.dirname(robotpath), "src") 
sys.path.insert(0, srcpath)

from netbots_log import log
from netbots_log import setLogLevel
import netbots_ipc as nbipc
import netbots_math as nbmath

robotName = "KevinBestBot"


def play(botSocket, srvConf):
    gameNumber = 0  # The last game number bot got from the server (0 == no game has been started)
    
    while True:
        
        currentMode = "start"
        turnDistance = srvConf['arenaSize'] / 5
        # The last direction we requested to go in.
        requestedDirection = None

        try:
            getLocationReply = botSocket.sendRecvMessage({'type': 'getLocationRequest'})
            if currentMode == "start":  # this will only be run once per game.
                # Find out which wall we are closest to and set best mode from that
                choices = [
                    ('left', getLocationReply['x']),  # distance to left wall
                    ('bottom', getLocationReply['y']),  # distance to bottom wall
                    ('right', srvConf['arenaSize'] - getLocationReply['x']),  # distance to right wall
                    ('top', srvConf['arenaSize'] - getLocationReply['y'])  # distance to top wall
                    ]

                pickMode = choices[0][0]
                pickDistance = choices[0][1]
                for i in range(1, len(choices)):
                    if choices[i][1] < pickDistance:
                        pickMode = choices[i][0]
                        pickDistance = choices[i][1]

                currentMode = pickMode
                log("Mode set to " + 
                    currentMode + 
                    " based on x = " + 
                    str(getLocationReply['x']) + 
                    ", y = " + 
                    str(getLocationReply['y']), "VERBOSE")

            # If we are too close to the wall we are moving towards to then switch mode so we turn.
            if currentMode == "left" and getLocationReply['y'] < turnDistance:
                # Moving along left wall and about to hit bottom wall.
                currentMode = "bottom"
                log("Mode set to " + currentMode + " based on y = " + str(getLocationReply['y']), "VERBOSE")
            elif currentMode == "bottom" and getLocationReply['x'] > srvConf['arenaSize'] - turnDistance:
                # Moving along bottom wall and about to hit right wall.
                currentMode = "right"
                log("Mode set to " + currentMode + " based on x = " + str(getLocationReply['x']), "VERBOSE")
            elif currentMode == "right" and getLocationReply['y'] > srvConf['arenaSize'] - turnDistance:
                # Moving along right wall and about to hit top wall.
                currentMode = "top"
                log("Mode set to " + currentMode + " based on y = " + str(getLocationReply['y']), "VERBOSE")
            elif currentMode == "top" and getLocationReply['x'] < turnDistance:
                # Moving along top wall and about to hit left wall.
                currentMode = "left"
                log("Mode set to " + currentMode + " based on x = " + str(getLocationReply['x']), "VERBOSE")

            if currentMode == "left":
                # closet to left wall so go down (counter clockwise around arena)
                newDirection = math.pi * 1.5
            elif currentMode == "bottom":
                # closet to bottom wall so go right (counter clockwise around arena)
                newDirection = 0
            elif currentMode == "right":
                # closet to right wall so go up (counter clockwise around arena)
                newDirection = math.pi * 0.5
            elif currentMode == "top":
                # closet to top wall so go left (counter clockwise around arena)
                newDirection = math.pi

            if newDirection != requestedDirection:
                # Turn in a new direction
                botSocket.sendRecvMessage({'type': 'setDirectionRequest', 'requestedDirection': newDirection})
                requestedDirection = newDirection
            botSocket.sendRecvMessage({'type': 'setSpeedRequest', 'requestedSpeed': 50})
           
            currentMode = "wait"  
            if currentMode == "wait":
                getCanonReply = botSocket.sendRecvMessage({'type':'getCanonRequest'})
                if not getCanonReply['shellInProgress']:
                    currentMode = "scan"
            if currentMode == "scan":
                binarySnipe(0, 128)
            
        except nbipc.NetBotSocketException as e:
            # Consider this a warning here. It may simply be that a request returned
            # an Error reply because our health == 0 since we last checked. We can
            # continue until the next game starts.
            continue

##################################################################
# Standard stuff below.
##################################################################


def binarySnipe(length, radius):
    if radius >= length:
        global currentMode
        global distance    
       
        mid = length + (radius - length) / 2
        if (mid <= length + 1):
            firedirection = ((((mid + length) / 2) / 128) * 2 * math.pi)
            currentMode = "wait"
            botSocket.sendRecvMessage({'type':'fireCanonRequest', 'direction': firedirection, 'distance' : distance})
        elif (mid >= radius - 1):
            firedirection = ((((mid + radius) / 2) / 128) * 2 * math.pi)
            currentMode = "wait"
            botSocket.sendRecvMessage({'type':'fireCanonRequest', 'direction': firedirection, 'distance' : distance})
        scanReply = botSocket.sendRecvMessage({'type':'scanRequest', 'startRadians':(length / 128) * 2 * math.pi, 'endRadians':(mid / 128) * 2 * math.pi})
        if(scanReply['distance'] != 0):
            distance = scanReply['distance']
            return binarySnipe(length, mid - 1)
        else:
            return binarySnipe(mid + 1, radius)
    else: 
        return -1

    
def quit(signal=None, frame=None):
    global botSocket
    log(botSocket.getStats())
    log("Quiting", "INFO")
    exit()


def main():
    global botSocket  # This is global so quit() can print stats in botSocket
    global robotName

    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-ip', metavar='My IP', dest='myIP', type=nbipc.argParseCheckIPFormat, nargs='?',
                        default='127.0.0.1', help='My IP Address')
    parser.add_argument('-p', metavar='My Port', dest='myPort', type=int, nargs='?',
                        default=20010, help='My port number')
    parser.add_argument('-sip', metavar='Server IP', dest='serverIP', type=nbipc.argParseCheckIPFormat, nargs='?',
                        default='127.0.0.1', help='Server IP Address')
    parser.add_argument('-sp', metavar='Server Port', dest='serverPort', type=int, nargs='?',
                        default=20000, help='Server port number')
    parser.add_argument('-debug', dest='debug', action='store_true',
                        default=False, help='Print DEBUG level log messages.')
    parser.add_argument('-verbose', dest='verbose', action='store_true',
                        default=False, help='Print VERBOSE level log messages. Note, -debug includes -verbose.')
    args = parser.parse_args()
    setLogLevel(args.debug, args.verbose)

    try:
        botSocket = nbipc.NetBotSocket(args.myIP, args.myPort, args.serverIP, args.serverPort)
        joinReply = botSocket.sendRecvMessage({'type': 'joinRequest', 'name': robotName}, retries=300, delay=1, delayMultiplier=1)
    except nbipc.NetBotSocketException as e:
        log("Is netbot server running at" + args.serverIP + ":" + str(args.serverPort) + "?")
        log(str(e), "FAILURE")
        quit()

    log("Join server was successful. We are ready to play!")

    # the server configuration tells us all about how big the arena is and other useful stuff.
    srvConf = joinReply['conf']
    log(str(srvConf), "VERBOSE")

    # Now we can play, but we may have to wait for a game to start.
    play(botSocket, srvConf)


if __name__ == "__main__":
    # execute only if run as a script
    signal.signal(signal.SIGINT, quit)
    main()
