#!/usr/bin/python
# -*- coding: utf-8 -*-
### See LICENSE and AUTHORS for details
# Copyright (c) 2017 Stephen Arnold <stephen.arnold42@gmail.com>
# Copyright (c) 2014 Jim Kemp <kemp.jim@gmail.com>

""" Fetches weather data from Weather.com for display on small screens."""

__version__ = "0.1.0"

###############################################################################
#   Raspberry Pi Weather Display
#    By: Jim Kemp    10/25/2014
#   PiTouch display hacks and schedulers
#    by: Steve Arnold  04/23/2017
###############################################################################
import os
import pygame
import time
import datetime
import random
from pygame.locals import *
import calendar
import pywapi
import string
# new lib dependencies - SLA
import sys
import signal
import schedule
import subprocess

from icon_defs import *
#import serial
#from X10 import *

# Setup GPIO pin BCM GPIO04
import RPi.GPIO as GPIO
GPIO.setmode( GPIO.BCM )
GPIO.setup( 4, GPIO.IN, pull_up_down=GPIO.PUD_DOWN )    # Next 
GPIO.setup( 17, GPIO.IN, pull_up_down=GPIO.PUD_DOWN )    # Shutdown

mouseX, mouseY = 0, 0
LEFT = True
mode = 'w'        # Default to weather mode.

# data refresh rate in minutes
data_refresh = 15

# enable backlight control for Pi Foundation display
# (note that extra_dim depends on backlight_control)
backlight_control = True
if backlight_control:
    # select tap mode, either exit or backlight on/off
    tap_mode = "backlight"

# enable display gamma dimming
extra_dim = False
dim_delay = 60
darken_value = 192

###############################################################################
def getIcon( w, i ):
    try:
        return int(w['forecasts'][i]['day']['icon'])
    except:
        return 29

# Small LCD Display.
class SmDisplay:
    screen = None;

    ####################################################################
    def __init__(self, keepalive=0):
        self.keepalive = keepalive
        "Ininitializes a new pygame screen using the framebuffer"
        # Based on "Python GUI in Linux frame buffer"
        # http://www.karoltomala.com/blog/?p=679
        disp_no = os.getenv("DISPLAY")
        if disp_no:
            print "X Display = {0}".format(disp_no)

        # Check which frame buffer drivers are available
        # Start with fbcon since directfb hangs with composite output
        drivers = ['x11', 'fbcon', 'directfb', 'svgalib']
        found = False
        for driver in drivers:
            # Make sure that SDL_VIDEODRIVER is set
            if not os.getenv('SDL_VIDEODRIVER'):
                os.putenv('SDL_VIDEODRIVER', driver)
            try:
                pygame.display.init()
            except pygame.error:
                print 'Driver: {0} failed.'.format(driver)
                continue
            found = True
            break

        if not found:
            raise Exception('No suitable video driver found!')
        
        size = (pygame.display.Info().current_w, pygame.display.Info().current_h)
        print "Framebuffer Size: %d x %d" % (size[0], size[1])
        self.screen = pygame.display.set_mode(size, pygame.FULLSCREEN)
        if self.keepalive:
            self.buffer = pygame.Surface(pygame.display.get_surface().get_size())
        else:
            self.buffer = None

        # Clear the screen to start
        self.screen.fill((0, 0, 0))
        # Initialise font support
        pygame.font.init()
        # Render the screen
        pygame.mouse.set_visible(0)
        pygame.display.update()

        #for fontname in pygame.font.get_fonts():
        #    print fontname
        self.temp = ''
        self.feels_like = 0
        self.wind_speed = 0
        self.baro = 0.0
        self.wind_dir = 'S'
        self.humid = 0
        self.wLastUpdate = ''
        self.day = [ '', '', '', '' ]
        self.icon = [ 0, 0, 0, 0 ]
        self.rain = [ '', '', '', '' ]
        self.temps = [ ['',''], ['',''], ['',''], ['',''] ]
        self.sunrise = '7:00 AM'
        self.sunset = '8:00 PM'

        # Larger Display
        self.xmax = 800 - 35
        self.ymax = 480 - 5
        self.scaleIcon = True         # Weather icons need scaling.
        self.iconScale = 1.5          # Icon scale amount.
        self.subwinTh = 0.05          # Sub window text height
        self.tmdateTh = 0.100         # Time & Date Text Height
        self.tmdateSmTh = 0.06
        self.tmdateYPos = 10          # Time & Date Y Position
        self.tmdateYPosSm = 18        # Time & Date Y Position Small

        """
        # Small Display
        self.xmax = 656 - 35
        self.ymax = 416 - 5
        self.scaleIcon = False        # No icon scaling needed.
        self.iconScale = 1.0
        self.subwinTh = 0.065        # Sub window text height
        self.tmdateTh = 0.125        # Time & Date Text Height
        self.tmdateSmTh = 0.075
        self.tmdateYPos = 1        # Time & Date Y Position
        self.tmdateYPosSm = 8        # Time & Date Y Position Small
        """


    ####################################################################
    def dim(self, darken_factor=darken_value, color_filter=(0,0,0)):
        if not self.keepalive:
            self.buffer = pygame.Surface(pygame.display.get_surface().get_size())
        self.buffer.blit(pygame.display.get_surface(),(0,0))
        if darken_factor > 0:
            darken=pygame.Surface(pygame.display.get_surface().get_size())
            darken.fill(color_filter)
            darken.set_alpha(darken_factor)
            # safe old clipping rectangle...
            old_clip = pygame.display.get_surface().get_clip()
            # ..blit over entire screen...
            pygame.display.get_surface().blit(darken,(0,0))
            pygame.display.flip()
            # ... and restore clipping
            pygame.display.get_surface().set_clip(old_clip)


    ####################################################################
    def undim(self):
        if self.buffer:
            pygame.display.get_surface().blit(self.buffer,(0,0))
            pygame.display.flip()
            if not self.keepalive:
                self.buffer=None


    ####################################################################
    def backlight_off(self):
        try:
            retcode = subprocess.call(["rpi-backlight", "off"])
            if retcode < 0:
                print >>sys.stderr, "Child process terminated:", -retcode
        except OSError as err:
            print >>sys.stderr, "Execution failed:", err


    ####################################################################
    def backlight_on(self):
        try:
            retcode = subprocess.call(["rpi-backlight", "on"])
            if retcode < 0:
                print >>sys.stderr, "Child process terminated:", -retcode
        except OSError as err:
            print >>sys.stderr, "Execution failed:", err


    ####################################################################
    def backlight_min(self):
        try:
            retcode = subprocess.call(["rpi-backlight", "min"])
            if retcode < 0:
                print >>sys.stderr, "Child process terminated:", -retcode
        except OSError as err:
            print >>sys.stderr, "Execution failed:", err


    ####################################################################
    def backlight_max(self):
        try:
            retcode = subprocess.call(["rpi-backlight", "max"])
            if retcode < 0:
                print >>sys.stderr, "Child process terminated:", -retcode
        except OSError as err:
            print >>sys.stderr, "Execution failed:", err


    ####################################################################
    def backlight_up(self):
        try:
            retcode = subprocess.call(["rpi-backlight", "up"])
            if retcode < 0:
                print >>sys.stderr, "Child process terminated:", -retcode
        except OSError as err:
            print >>sys.stderr, "Execution failed:", err


    ####################################################################
    def backlight_down(self):
        try:
            retcode = subprocess.call(["rpi-backlight", "down"])
            if retcode < 0:
                print >>sys.stderr, "Child process terminated:", -retcode
        except OSError as err:
            print >>sys.stderr, "Execution failed:", err


    ####################################################################
    def __del__(self):
        "Destructor to make sure pygame shuts down, etc."


    ####################################################################
    def disp_weather(self):
        # Fill the screen with black
        self.screen.fill( (0,0,0) )
        xmin = 10
        xmax = self.xmax
        ymax = self.ymax
        lines = 5
        lc = (255,255,255) 
        fn = "freesans"

        # Draw Screen Border
        pygame.draw.line( self.screen, lc, (xmin,0),(xmax,0), lines )
        pygame.draw.line( self.screen, lc, (xmin,0),(xmin,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax),(xmax,ymax), lines )    # Bottom
        pygame.draw.line( self.screen, lc, (xmax,0),(xmax,ymax+2), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax*0.15),(xmax,ymax*0.15), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax*0.5),(xmax,ymax*0.5), lines )
        pygame.draw.line( self.screen, lc, (xmax*0.25,ymax*0.5),(xmax*0.25,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmax*0.5,ymax*0.15),(xmax*0.5,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmax*0.75,ymax*0.5),(xmax*0.75,ymax), lines )

        # Time & Date
        th = self.tmdateTh
        sh = self.tmdateSmTh
        font = pygame.font.SysFont( fn, int(ymax*th), bold=1 )     # Regular Font
        sfont = pygame.font.SysFont( fn, int(ymax*sh), bold=1 )    # Small Font for Seconds

        tm1 = time.strftime( "%a, %b %d   %I:%M", time.localtime() )    # 1st part
        tm2 = time.strftime( "%S", time.localtime() )                   # 2nd
        tm3 = time.strftime( " %P", time.localtime() )                  # 

        rtm1 = font.render( tm1, True, lc )
        (tx1,ty1) = rtm1.get_size()
        rtm2 = sfont.render( tm2, True, lc )
        (tx2,ty2) = rtm2.get_size()
        rtm3 = font.render( tm3, True, lc )
        (tx3,ty3) = rtm3.get_size()

        tp = xmax / 2 - (tx1 + tx2 + tx3) / 2
        self.screen.blit( rtm1, (tp,self.tmdateYPos) )
        self.screen.blit( rtm2, (tp+tx1+3,self.tmdateYPosSm) )
        self.screen.blit( rtm3, (tp+tx1+tx2,self.tmdateYPos) )

        # Outside Temp
        font = pygame.font.SysFont( fn, int(ymax*(0.5-0.15)*0.9), bold=1 )
        txt = font.render( self.temp, True, lc )
        (tx,ty) = txt.get_size()
        # Show degree F symbol using magic unicode char in a smaller font size.
        dfont = pygame.font.SysFont( fn, int(ymax*(0.5-0.15)*0.5), bold=1 )
        dtxt = dfont.render( unichr(0x2109), True, lc )
        (tx2,ty2) = dtxt.get_size()
        x = xmax*0.27 - (tx*1.02 + tx2) / 2
        self.screen.blit( txt, (x,ymax*0.15) )
        #self.screen.blit( txt, (xmax*0.02,ymax*0.15) )
        x = x + (tx*1.02)
        self.screen.blit( dtxt, (x,ymax*0.2) )
        #self.screen.blit( dtxt, (xmax*0.02+tx*1.02,ymax*0.2) )

        # Conditions
        st = 0.16    # Yaxis Start Pos
        gp = 0.065   # Line Spacing Gap
        th = 0.06    # Text Height
        dh = 0.05    # Degree Symbol Height
        so = 0.01    # Degree Symbol Yaxis Offset
        xp = 0.52    # Xaxis Start Pos
        x2 = 0.78    # Second Column Xaxis Start Pos

        font = pygame.font.SysFont( fn, int(ymax*th), bold=1 )
        txt = font.render( 'Windchill:', True, lc )
        self.screen.blit( txt, (xmax*xp,ymax*st) )
        txt = font.render( self.feels_like, True, lc )
        self.screen.blit( txt, (xmax*x2,ymax*st) )
        (tx,ty) = txt.get_size()
        # Show degree F symbol using magic unicode char.
        dfont = pygame.font.SysFont( fn, int(ymax*dh), bold=1 )
        dtxt = dfont.render( unichr(0x2109), True, lc )
        self.screen.blit( dtxt, (xmax*x2+tx*1.01,ymax*(st+so)) )

        txt = font.render( 'Windspeed:', True, lc )
        self.screen.blit( txt, (xmax*xp,ymax*(st+gp*1)) )
        txt = font.render( self.wind_speed+' mph', True, lc )
        self.screen.blit( txt, (xmax*x2,ymax*(st+gp*1)) )

        txt = font.render( 'Direction:', True, lc )
        self.screen.blit( txt, (xmax*xp,ymax*(st+gp*2)) )
        txt = font.render( string.upper(self.wind_dir), True, lc )
        self.screen.blit( txt, (xmax*x2,ymax*(st+gp*2)) )

        txt = font.render( 'Barometer:', True, lc )
        self.screen.blit( txt, (xmax*xp,ymax*(st+gp*3)) )
        txt = font.render( self.baro + '"Hg', True, lc )
        self.screen.blit( txt, (xmax*x2,ymax*(st+gp*3)) )

        txt = font.render( 'Humidity:', True, lc )
        self.screen.blit( txt, (xmax*xp,ymax*(st+gp*4)) )
        txt = font.render( self.humid+'%', True, lc )
        self.screen.blit( txt, (xmax*x2,ymax*(st+gp*4)) )

        wx =     0.125            # Sub Window Centers
        wy =     0.510            # Sub Windows Yaxis Start
        th =     self.subwinTh    # Text Height
        rpth =   0.100            # Rain Present Text Height
        gp =     0.065            # Line Spacing Gap
        ro =     0.010 * xmax     # "Rain:" Text Window Offset within window. 
        rpl =    5.95             # Rain percent line offset.

        font = pygame.font.SysFont( fn, int(ymax*th), bold=1 )
        rpfont = pygame.font.SysFont( fn, int(ymax*rpth), bold=1 )

        # Sub Window 1
        txt = font.render( 'Today:', True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*wx-tx/2,ymax*(wy+gp*0)) )
        txt = font.render( self.temps[0][0] + ' / ' + self.temps[0][1], True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*wx-tx/2,ymax*(wy+gp*5)) )
        #rtxt = font.render( 'Rain:', True, lc )
        #self.screen.blit( rtxt, (ro,ymax*(wy+gp*5)) )
        rptxt = rpfont.render( self.rain[0]+'%', True, lc )
        (tx,ty) = rptxt.get_size()
        self.screen.blit( rptxt, (xmax*wx-tx/2,ymax*(wy+gp*rpl)) )
        icon = pygame.image.load(sd + icons[self.icon[0]]).convert_alpha()
        (ix,iy) = icon.get_size()
        if self.scaleIcon:
            icon2 = pygame.transform.scale( icon, (int(ix*1.5),int(iy*1.5)) )
            (ix,iy) = icon2.get_size()
            icon = icon2
        if ( iy < 90 ):
            yo = (90 - iy) / 2 
        else: 
            yo = 0
        self.screen.blit( icon, (xmax*wx-ix/2,ymax*(wy+gp*1.2)+yo) )

        # Sub Window 2
        txt = font.render( self.day[1]+':', True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*(wx*3)-tx/2,ymax*(wy+gp*0)) )
        txt = font.render( self.temps[1][0] + ' / ' + self.temps[1][1], True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*wx*3-tx/2,ymax*(wy+gp*5)) )
        #self.screen.blit( rtxt, (xmax*wx*2+ro,ymax*(wy+gp*5)) )
        rptxt = rpfont.render( self.rain[1]+'%', True, lc )
        (tx,ty) = rptxt.get_size()
        self.screen.blit( rptxt, (xmax*wx*3-tx/2,ymax*(wy+gp*rpl)) )
        icon = pygame.image.load(sd + icons[self.icon[1]]).convert_alpha()
        (ix,iy) = icon.get_size()
        if self.scaleIcon:
            icon2 = pygame.transform.scale( icon, (int(ix*1.5),int(iy*1.5)) )
            (ix,iy) = icon2.get_size()
            icon = icon2
        if ( iy < 90 ):
            yo = (90 - iy) / 2 
        else: 
            yo = 0
        self.screen.blit( icon, (xmax*wx*3-ix/2,ymax*(wy+gp*1.2)+yo) )

        # Sub Window 3
        txt = font.render( self.day[2]+':', True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*(wx*5)-tx/2,ymax*(wy+gp*0)) )
        txt = font.render( self.temps[2][0] + ' / ' + self.temps[2][1], True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*wx*5-tx/2,ymax*(wy+gp*5)) )
        #self.screen.blit( rtxt, (xmax*wx*4+ro,ymax*(wy+gp*5)) )
        rptxt = rpfont.render( self.rain[2]+'%', True, lc )
        (tx,ty) = rptxt.get_size()
        self.screen.blit( rptxt, (xmax*wx*5-tx/2,ymax*(wy+gp*rpl)) )
        icon = pygame.image.load(sd + icons[self.icon[2]]).convert_alpha()
        (ix,iy) = icon.get_size()
        if self.scaleIcon:
            icon2 = pygame.transform.scale( icon, (int(ix*1.5),int(iy*1.5)) )
            (ix,iy) = icon2.get_size()
            icon = icon2
        if ( iy < 90 ):
            yo = (90 - iy) / 2 
        else: 
            yo = 0
        self.screen.blit( icon, (xmax*wx*5-ix/2,ymax*(wy+gp*1.2)+yo) )

        # Sub Window 4
        txt = font.render( self.day[3]+':', True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*(wx*7)-tx/2,ymax*(wy+gp*0)) )
        txt = font.render( self.temps[3][0] + ' / ' + self.temps[3][1], True, lc )
        (tx,ty) = txt.get_size()
        self.screen.blit( txt, (xmax*wx*7-tx/2,ymax*(wy+gp*5)) )
        #self.screen.blit( rtxt, (xmax*wx*6+ro,ymax*(wy+gp*5)) )
        rptxt = rpfont.render( self.rain[3]+'%', True, lc )
        (tx,ty) = rptxt.get_size()
        self.screen.blit( rptxt, (xmax*wx*7-tx/2,ymax*(wy+gp*rpl)) )
        icon = pygame.image.load(sd + icons[self.icon[3]]).convert_alpha()
        (ix,iy) = icon.get_size()
        if self.scaleIcon:
            icon2 = pygame.transform.scale( icon, (int(ix*1.5),int(iy*1.5)) )
            (ix,iy) = icon2.get_size()
            icon = icon2
        if ( iy < 90 ):
            yo = (90 - iy) / 2 
        else: 
            yo = 0
        self.screen.blit( icon, (xmax*wx*7-ix/2,ymax*(wy+gp*1.2)+yo) )

        # Update the display
        pygame.display.update()

    ####################################################################
    def disp_calendar(self):
        # Fill the screen with black
        self.screen.fill( (0,0,0) )
        xmin = 10
        xmax = self.xmax
        ymax = self.ymax
        lines = 5
        lc = (255,255,255) 
        sfn = "freemono"
        fn = "freesans"

        # Draw Screen Border
        pygame.draw.line( self.screen, lc, (xmin,0),(xmax,0), lines )
        pygame.draw.line( self.screen, lc, (xmin,0),(xmin,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax),(xmax,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmax,0),(xmax,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax*0.15),(xmax,ymax*0.15), lines )

        # Time & Date
        th = self.tmdateTh
        sh = self.tmdateSmTh
        font = pygame.font.SysFont( fn, int(ymax*th), bold=1 )        # Regular Font
        sfont = pygame.font.SysFont( fn, int(ymax*sh), bold=1 )    # Small Font for Seconds

        tm1 = time.strftime( "%a, %b %d   %I:%M", time.localtime() )    # 1st part
        tm2 = time.strftime( "%S", time.localtime() )            # 2nd
        tm3 = time.strftime( " %P", time.localtime() )            # 

        rtm1 = font.render( tm1, True, lc )
        (tx1,ty1) = rtm1.get_size()
        rtm2 = sfont.render( tm2, True, lc )
        (tx2,ty2) = rtm2.get_size()
        rtm3 = font.render( tm3, True, lc )
        (tx3,ty3) = rtm3.get_size()

        tp = xmax / 2 - (tx1 + tx2 + tx3) / 2
        self.screen.blit( rtm1, (tp,self.tmdateYPos) )
        self.screen.blit( rtm2, (tp+tx1+3,self.tmdateYPosSm) )
        self.screen.blit( rtm3, (tp+tx1+tx2,self.tmdateYPos) )

        # Conditions
        ys = 0.20        # Yaxis Start Pos
        xs = 0.20        # Xaxis Start Pos
        gp = 0.075       # Line Spacing Gap
        th = 0.05        # Text Height

        #cal = calendar.TextCalendar()
        yr = int( time.strftime( "%Y", time.localtime() ) )    # Get Year
        mn = int( time.strftime( "%m", time.localtime() ) )    # Get Month
        cal = calendar.month( yr, mn ).splitlines()
        i = 0
        for cal_line in cal:
            txt = sfont.render( cal_line, True, lc )
            self.screen.blit( txt, (xmax*xs,ymax*(ys+gp*i)) )
            i = i + 1

        # Update the display
        pygame.display.update()

    ####################################################################
    def sPrint( self, s, font, x, l, lc ):
        f = font.render( s, True, lc )
        self.screen.blit( f, (x,self.ymax*0.075*l) )

    ####################################################################
    def disp_help( self, inDaylight, dayHrs, dayMins, tDaylight, tDarkness ):
        # Fill the screen with black
        self.screen.fill( (0,0,0) )
        xmax = self.xmax
        ymax = self.ymax
        xmin = 10
        lines = 5
        lc = (255,255,255) 
        sfn = "freemono"
        fn = "freesans"

        # Draw Screen Border
        pygame.draw.line( self.screen, lc, (xmin,0),(xmax,0), lines )
        pygame.draw.line( self.screen, lc, (xmin,0),(xmin,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax),(xmax,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmax,0),(xmax,ymax), lines )
        pygame.draw.line( self.screen, lc, (xmin,ymax*0.15),(xmax,ymax*0.15), lines )

        thl = self.tmdateTh    # Large Text Height
        sh = self.tmdateSmTh    # Small Text Height

        # Time & Date
        font = pygame.font.SysFont( fn, int(ymax*thl), bold=1 )  # Regular Font
        sfont = pygame.font.SysFont( fn, int(ymax*sh), bold=1 )  # Small Font

        tm1 = time.strftime( "%a, %b %d   %I:%M", time.localtime() )  # 1st part
        tm2 = time.strftime( "%S", time.localtime() )                 # 2nd
        tm3 = time.strftime( " %P", time.localtime() )                # 3rd

        rtm1 = font.render( tm1, True, lc )
        (tx1,ty1) = rtm1.get_size()
        rtm2 = sfont.render( tm2, True, lc )
        (tx2,ty2) = rtm2.get_size()
        rtm3 = font.render( tm3, True, lc )
        (tx3,ty3) = rtm3.get_size()

        tp = xmax / 2 - (tx1 + tx2 + tx3) / 2
        self.screen.blit( rtm1, (tp,self.tmdateYPos) )
        self.screen.blit( rtm2, (tp+tx1+3,self.tmdateYPosSm) )
        self.screen.blit( rtm3, (tp+tx1+tx2,self.tmdateYPos) )

        self.sPrint( "Sunrise: %s" % self.sunrise, sfont, xmax*0.05, 3, lc )
        self.sPrint( "Sunset: %s" % self.sunset, sfont, xmax*0.05, 4, lc )

        s = "Daylight (Hrs:Min): %d:%02d" % (dayHrs, dayMins)
        self.sPrint( s, sfont, xmax*0.05, 5, lc )

        if inDaylight: s = "Sunset in (Hrs:Min): %d:%02d" % stot( tDarkness )
        else:          s = "Sunrise in (Hrs:Min): %d:%02d" % stot( tDaylight )
        self.sPrint( s, sfont, xmax*0.05, 6, lc )

        s = "Update: %s" % self.wLastUpdate
        self.sPrint( s, sfont, xmax*0.05, 7, lc )

        cc = 'current_conditions'
        s = "Current Cond: %s" % self.w[cc]['text']
        self.sPrint( s, sfont, xmax*0.05, 8, lc )
        
        # Outside Temperature
        s = self.temp + unichr(176) + 'F '
        s = s + self.baro + 'inHg '
        s = s + 'Wind ' + self.wind_speed
        if self.gust != 'N/A': 
            s = s + '/' + self.gust
        if self.wind_speed != 'calm':
            s = s + 'mph @' + self.wind_direction + unichr(176)
        self.sPrint( s, sfont, xmax*0.05, 9, lc )

        s = "Visability %smi" % self.vis
        self.sPrint( s, sfont, xmax*0.05, 10, lc )

        # Update the display
        pygame.display.update()


    # Save a jpg image of the screen.
    ####################################################################
    def screen_cap( self ):
        pygame.image.save( self.screen, "screenshot.jpeg" )
        print "Screen capture complete."


    ####################################################################
    def UpdateWeather( self ):
        # Use Weather.com for source data.
        cc = 'current_conditions'
        f = 'forecasts'

        # This is where the magic happens. 
        self.w = pywapi.get_weather_from_weather_com( '93455', units='imperial' )
        w = self.w
        try:
            if ( w[cc]['last_updated'] != self.wLastUpdate ):
                self.wLastUpdate = w[cc]['last_updated']
                print "Last Weather Update: " + self.wLastUpdate
                self.temp = string.lower( w[cc]['temperature'] )
                self.feels_like = string.lower( w[cc]['feels_like'] )
                self.wind_speed = string.lower( w[cc]['wind']['speed'] )
                self.baro = string.lower( w[cc]['barometer']['reading'] )
                self.wind_dir = string.upper( w[cc]['wind']['text'] )
                self.humid = string.upper( w[cc]['humidity'] )
                self.vis = string.upper( w[cc]['visibility'] )
                self.gust = string.upper( w[cc]['wind']['gust'] )
                self.wind_direction = string.upper( w[cc]['wind']['direction'] )
                self.day[0] = w[f][0]['day_of_week']
                self.day[1] = w[f][1]['day_of_week']
                self.day[2] = w[f][2]['day_of_week']
                self.day[3] = w[f][3]['day_of_week']
                self.sunrise = w[f][0]['sunrise']
                self.sunset = w[f][0]['sunset']
                self.icon[0] = getIcon( w, 0 )
                self.icon[1] = getIcon( w, 1 )
                self.icon[2] = getIcon( w, 2 )
                self.icon[3] = getIcon( w, 3 )
                print 'Icon Index: ', self.icon[0], self.icon[1], self.icon[2], self.icon[3]
                #print 'File: ', sd+icons[self.icon[0]]
                self.rain[0] = w[f][0]['day']['chance_precip']
                self.rain[1] = w[f][1]['day']['chance_precip']
                self.rain[2] = w[f][2]['day']['chance_precip']
                self.rain[3] = w[f][3]['day']['chance_precip']
                if ( w[f][0]['high'] == 'N/A' ):
                    self.temps[0][0] = '--'
                else:
                    self.temps[0][0] = w[f][0]['high'] + unichr(0x2109)
                self.temps[0][1] = w[f][0]['low'] + unichr(0x2109)
                self.temps[1][0] = w[f][1]['high'] + unichr(0x2109)
                self.temps[1][1] = w[f][1]['low'] + unichr(0x2109)
                self.temps[2][0] = w[f][2]['high'] + unichr(0x2109)
                self.temps[2][1] = w[f][2]['low'] + unichr(0x2109)
                self.temps[3][0] = w[f][3]['high'] + unichr(0x2109)
                self.temps[3][1] = w[f][3]['low'] + unichr(0x2109)
        except KeyError:
            print "KeyError -> Weather Error"
            self.temp = '??'
            self.wLastUpdate = ''
            return False
        #except ValueError:
        #    print "ValueError -> Weather Error"

        return True


# Helper function to which takes seconds and returns (hours, minutes).
############################################################################
def stot( sec ):
    min = sec.seconds // 60
    hrs = min // 60
    return ( hrs, min % 60 )


# another helper function for python2
def sigpipe_fix():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)


# Given a sunrise and sunset time string (sunrise example format '7:00 AM'),
# return true if current local time is between sunrise and sunset. In other
# words, return true if it's daytime and the sun is up. Also, return the 
# number of hours:minutes of daylight in this day. Lastly, return the number
# of seconds until daybreak and sunset. If it's dark, daybreak is set to the 
# number of seconds until sunrise. If it's daytime, sunset is set to the number
# of seconds until the sun sets.
# 
# So, five things are returned as:
#  ( InDaylight, Hours, Minutes, secToSun, secToDark).
# 
# SLA - 04/22/2017 - Make that seven things
#    Add sunrise and sunset time objects for scheduling
#    (where tSunset is the time *of* sunset, same for tSunrise)
############################################################################
def Daylight( sr, st ):
    inDaylight = False    # Default return code.

    # Get current datetime with tz's local day and time.
    tNow = datetime.datetime.now()

    # From a string like '7:00 AM', build a datetime variable for
    # today with the hour and minute set to sunrise.
    t = time.strptime( sr, '%I:%M %p' )        # Temp Var
    tSunrise = tNow                    # Copy time now.
    # Overwrite hour and minute with sunrise hour and minute.
    tSunrise = tSunrise.replace( hour=t.tm_hour, minute=t.tm_min, second=0 )

    # From a string like '8:00 PM', build a datetime variable for
    # today with the hour and minute set to sunset.
    t = time.strptime( myDisp.sunset, '%I:%M %p' )
    tSunset = tNow                    # Copy time now.
    # Overwrite hour and minute with sunset hour and minute.
    tSunset = tSunset.replace( hour=t.tm_hour, minute=t.tm_min, second=0 )

    # Test if current time is between sunrise and sunset.
    if (tNow > tSunrise) and (tNow < tSunset):
        inDaylight = True        # We're in Daytime
        tDarkness = tSunset - tNow    # Delta seconds until dark.
        tDaylight = 0            # Seconds until daylight
    else:
        inDaylight = False        # We're in Nighttime
        tDarkness = 0            # Seconds until dark.
        # Delta seconds until daybreak.
        if tNow > tSunset:
            # Must be evening - compute sunrise as time left today
            # plus time from midnight tomorrow.
            tMidnight = tNow.replace( hour=23, minute=59, second=59 )
            tNext = tNow.replace( hour=0, minute=0, second=0 )
            tDaylight = (tMidnight - tNow) + (tSunrise - tNext)
        else:
            # Else, must be early morning hours. Time to sunrise is 
            # just the delta between sunrise and now.
            tDaylight = tSunrise - tNow

    # Compute the delta time (in seconds) between sunrise and set.
    dDaySec = tSunset - tSunrise        # timedelta in seconds
    (dayHrs, dayMin) = stot( dDaySec )  # split into hours and minutes.

    return (inDaylight, dayHrs, dayMin,
            tDaylight, tDarkness,
            tSunrise, tSunset)


############################################################################
def btnNext( channel ):
    global mode, dispTO

    if ( mode == 'c' ): mode = 'w'
    elif (mode == 'w' ): mode ='h'
    elif (mode == 'h' ): mode ='c'

    dispTO = 0

    print "Button Event!"


#==============================================================
#==============================================================

try:
    ser = serial.Serial( "/dev/ttyUSB0", 4800, timeout=2 )
    serActive = True
except:
    serActive = False
    print "Warning: can't open ttyUSB0 serial port."

if serActive:
    X10 = False        # Assume no X10 until proven wrong.
    ser.flushInput()    # Dump any junk that may be there.
    ser.flushOutput()

    ser.write( chr(0x8b) )    # Querry Status
    c = ser.read( 1 )    # Wait for something from the CM11A.

    # If an attached CM11A sends a 0xA5 then it requires a clock reset.
    if (len(c) == 1):
        if (ord(c) == 0xA5):
            X10_SetClock( ser )
    else:
        time.sleep( 0.5 )

    # Get the current status from the CM11A X10 module.
    (X10, c) = X10_Status( ser )

    if X10 == False: print 'Error: CM11A.'

    # If CM11A is present, turn on the lamp A3!
    if X10 == True:
        if X10_On( ser, housecode['A'], unitcode['3'] ):
            print 'X10 On comand OK.'
        else:
            print 'Error in X10 On command.'
        time.sleep( 2 )
        if X10_Bright( ser, housecode['A'], unitcode['3'] ):
            print 'X10 Full Bright OK.'
        else:
            print 'Error in X10 Bright command.'


mode = 'w'        # Default to weather mode.

# Create an instance of the lcd display class.
myDisp = SmDisplay(keepalive=1)

# Load data from Weather.com into class variables and schedules jobs
if myDisp.UpdateWeather() == False:
    print 'Error: no data from Weather.com.'
    running = False
else:
    # retreive WX data and set the update scheduler
    myDisp.UpdateWeather()
    schedule.every(data_refresh).minutes.do(myDisp.UpdateWeather)
    # retrieve and format times for display dimming
    #  note scheduler times must be a string with format HH:MM
    (inDaylight, dayHrs, dayMins, tDaylight, tDarkness, tSunrise, tSunset) = Daylight(myDisp.sunrise, myDisp.sunset)
    riseTime = tSunrise.strftime('%H:%M')
    setTime = tSunset.strftime('%H:%M')
    delayTime = tSunset + datetime.timedelta(minutes=dim_delay)
    dimTime = delayTime.strftime('%H:%M')
    # set display schedulers and update display state
    if backlight_control:
        schedule.every().day.at(riseTime).do(myDisp.backlight_max)
        schedule.every().day.at(setTime).do(myDisp.backlight_min)
        if not inDaylight:
            myDisp.backlight_min()
        else:
            myDisp.backlight_max()
        # TODO fix dimming so it runs during display loop
        if extra_dim:
            schedule.every().day.at(riseTime).do(myDisp.undim)
            schedule.every().day.at(dimTime).do(myDisp.dim)
            if not inDaylight:
                myDisp.dim()

# Attach GPIO callback to our new button input on pin #4.
GPIO.add_event_detect( 4, GPIO.RISING, callback=btnNext, bouncetime=400)
#GPIO.add_event_detect( 17, GPIO.RISING, callback=btnShutdown, bouncetime=100)
btnShutdownCnt = 0

if GPIO.input( 17 ):
    print "Warning: Shutdown Switch is Active!"
    myDisp.screen.fill( (0,0,0) )
    icon = pygame.image.load(sd + 'shutdown.jpg')
    (ix,iy) = icon.get_size()
    myDisp.screen.blit( icon, (800/2-ix/2,400/2-iy/2) )
    font = pygame.font.SysFont( "freesans", 40, bold=1 )
    rf = font.render( "Please toggle shutdown siwtch.", True, (255,255,255) )
    (tx1,ty1) = rf.get_size()
    myDisp.screen.blit( rf, (800/2-tx1/2,iy+20) )
    pygame.display.update()
    pygame.time.wait( 1000 )
    while GPIO.input( 17 ): pygame.time.wait(100)


firstClick = None   # set default for double-tap
running = True      # Stay running while True
s = None            # Seconds Placeholder to pace display.
dispTO = 0          # Display timeout to automatically switch back to weather
                    # display.

#+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
try:
    while running:

        # start data update and display scheduler
        schedule.run_pending()

        # Debounce the shutdown switch. The main loop runs at 100ms. So, if the 
        # button (well, a switch really) counter "btnShutdownCnt" counts above
        # 25 then the switch must have been on continuously for 2.5 seconds.
        if GPIO.input( 17 ):
            btnShutdownCnt += 1
            if btnShutdownCnt > 25:
                print "Shutdown!"
                myDisp.screen.fill( (0,0,0) )
                icon = pygame.image.load(sd + 'shutdown.jpg')
                (ix,iy) = icon.get_size()
                myDisp.screen.blit( icon, (800/2-ix/2,400/2-iy/2) )
                font = pygame.font.SysFont( "freesans", 60, bold=1 )
                rtm1 = font.render( "Shuting Down!", True, (255,255,255) )
                (tx1,ty1) = rtm1.get_size()
                myDisp.screen.blit( rtm1, (800/2-tx1/2,iy+20) )
                pygame.display.update()
                pygame.time.wait( 1000 )
                #os.system("sudo shutdown -h now")
                while GPIO.input( 17 ): pygame.time.wait(100)
        else:
            btnShutdownCnt = 0

        # Look for and process keyboard events to change modes.
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                # On 'q' or keypad enter key, quit the program.
                if (( event.key == K_KP_ENTER ) or (event.key == K_q)):
                    running = False

                # brighten backlight by 10 percent on keypad '+' or 'u' key
                elif (( event.key == K_KP_PLUS ) or (event.key == K_u)):
                    myDisp.backlight_up()

                # dim backlight by 10 percent on keypad '-' or 'd' key
                elif (( event.key == K_KP_MINUS ) or (event.key == K_d)):
                    myDisp.backlight_down()

                # On 'c' key, set mode to 'calendar'.
                elif ( event.key == K_c ):
                    mode = 'c'
                    dispTO = 0

                # On 'w' key, set mode to 'weather'.
                elif ( event.key == K_w ):
                    mode = 'w'
                    dispTO = 0

                # On 's' key, save a screen shot.
                elif ( event.key == K_s ):
                    myDisp.screen_cap()

                # On 'h' key, set mode to 'help'.
                elif ( event.key == K_h ):
                    mode = 'h'
                    dispTO = 0

            # keep track of screen tap (mouse click) for 500 ms so we
            # recognize a double-tap to quit (delay is printed below)
            if event.type == pygame.MOUSEBUTTONDOWN:
                if firstClick:
                    #print "Click delay %d ms" % (pygame.time.get_ticks() - firstClick)
                    if tap_mode == "backlight":
                        myDisp.backlight_off()
                    else:
                        running = False    # Quit on double-click
                else:
                    firstClick = pygame.time.get_ticks()

            if firstClick and (pygame.time.get_ticks() - firstClick) > 500:
                if tap_mode == "backlight":
                    myDisp.backlight_on()
                    firstClick = None
                else:
                    firstClick = None

        # Automatically switch between weather display and help display
        if mode != 'w':
            dispTO += 1
            if dispTO > 595:    # approx one minute timeout at 100ms loop rate.
                mode = 'w'
        else:
            dispTO = 0

        # Calendar Display Mode
        # TODO fix alignment
        if ( mode == 'c' ):
            # Update / Refresh the display after each second.
            if ( s != time.localtime().tm_sec ):
                s = time.localtime().tm_sec
                myDisp.disp_calendar()

        # Weather Display Mode
        if ( mode == 'w' ):
            # Update / Refresh the display after each second.
            if ( s != time.localtime().tm_sec ):
                s = time.localtime().tm_sec

                ( inDaylight, dayHrs, dayMins, tDaylight, tDarkness, tSunrise, tSunset ) = Daylight( myDisp.sunrise, myDisp.sunset )

                myDisp.disp_weather()
                #ser.write( "Weather\r\n" )
            if ( int(s) == 0 ):
                # switch between 'h' and 'w'
                mode = 'h'

        if ( mode == 'h'):
            # Pace the screen updates to once per second.
            if s != time.localtime().tm_sec:
                s = time.localtime().tm_sec

                ( inDaylight, dayHrs, dayMins, tDaylight, tDarkness, tSunrise, tSunset ) = Daylight( myDisp.sunrise, myDisp.sunset )

                #if inDaylight:
                #    print "Time until dark (Hr:Min) -> %d:%d" % stot( tDarkness )
                #else:
                #    #print 'tDaylight ->', tDaylight
                #    print "Time until daybreak (Hr:Min) -> %d:%d" % stot( tDaylight )

                # Stat Screen Display.
                myDisp.disp_help( inDaylight, dayHrs, dayMins, tDaylight, tDarkness )

        # get daylight times for X10 interface
        #( inDaylight, dayHrs, dayMins, tDaylight, tDarkness) = Daylight( myDisp.sunrise, myDisp.sunset )

        # TODO make X10 commands scheduler driven
        if serActive:    
            h = housecode['A']
            u = unitcode['3']

            if time.localtime().tm_sec == 30:
                if ( inDaylight == False ): 
                    X10_On( ser, h, u )
                    print "X10 On"
                else: 
                    X10_Off( ser, h, u )
                    print "X10 Off"
            if time.localtime().tm_sec == 40:
                if ( inDaylight == False ):
                    X10_Bright( ser, housecode['A'], unitcode['3'] )

        # Loop timer.
        pygame.time.wait( 100 )

except KeyboardInterrupt:
    print("")
    print("Clearing job queue and restoring display")
    schedule.clear()
    if backlight_control:
        if inDaylight:
            subprocess.call(["rpi-backlight", "max"])
        else:
            subprocess.call(["rpi-backlight", "min"])

finally:
    pygame.quit()
