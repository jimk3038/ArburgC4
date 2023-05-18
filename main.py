# =============================================================================
#
#	Arburg Injection Molder - Raspberry Pi Controller
#
#	By: Jim Kemp	9/9/2018
#
#	v2.1 10/9/2018 JKemp : Added "MoldOpenDelay" to settings to allow easy 
#	changes to the value.  The value 'MoldOpenDelay' forces a min delay time for 
#	the mold to hold open to allow part(s) to fall out of the mold.
#
#	5/19/2022 JKemp : Added double pump logic to eject cycle.  Not the best code.
#	Logic needs rewrite and a on/off button needs added to enable and disable.
#
# =============================================================================
import kivy
#kivy.require('1.0.5')

from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.app import App
from kivy.properties import *
from kivy.uix.textinput import TextInput
from kivy.core.window import Window 
from kivy.clock import Clock
from kivy.config import Config

from SevenSeg_Disp import Segment

from gpiozero import LED, Button
import Adafruit_GPIO.SPI as SPI
import MAX6675.MAX6675 as MAX6675

from pypref import Preferences
pref = Preferences(filename="settings.py")
# create preferences dict example
#pdict = { 'MaxTime': 45, 'CycleTm': 15.0, 'InjTm': 10.0, 'SetPt': 225 }
#pref.set_preferences(pdict)

from time import localtime, strftime

print "SetPt: ", pref.get('SetPt')

# The MAX6675 is a SPI based thermocouple interface chip.  The MAX6675 handles
# reading a K type thermocouple.  Also handles cold junction compensation.
tempTC = MAX6675.MAX6675( spi=SPI.SpiDev( 0, 0 ) )

Config.set('graphics', 'width', '800')
Config.set('graphics', 'height', '480')
Config.write()
Window.size = (800, 480)

# Setup the GPIO.
close = LED(6, active_high=True )
close.off()
inj = LED( 13, active_high=True )
inj.off()
heater = LED( 19, active_high=True )		# Heater Band relay output.
heater.off()
blowOff = LED( 5, active_high=True )		# Blow Off (part eject) Air Cylinder
blowOff.off()
estopOut = LED( 20 )						# Output for estop detection.
estopOut.off()
estop = Button( 21, pull_up=True )			# E-Stop Input
partDet = Button( 16, pull_up=True )		# Part Shoot Detect Switch
ups = Button( 26, pull_up=True )			# Detects power loss so we can shutdown.


# Builds the main window for everything else to live inside of.
# =============================================================================
class MainWindow( FloatLayout ):

	# The cycleStart, closeSol, and injSol disabled state are all tied
	# to this one kivy property.  Setting this True disables them all.
	abortDisabled = BooleanProperty( True )

	# Used to control the enable state of the cycle start button.
	autoStop = BooleanProperty( False )

	# Temperature setpoint for the heater bands.
	# Get value from settings.py file.
	tempSetPt = NumericProperty( pref.get('SetPt', default=200) )	

	tempSensor = NumericProperty( 80 )	# Temperature on the thermocouple.

	# This is the output percent value for the heater bands.
	heaterOut = NumericProperty( 0 )	# Default to 0%

	# Keeps track of current cycle time.
	timer = NumericProperty( 0.0 )

	tempLblColor = ListProperty( (1,0,0,1) )

	# Controls the length of the sliders for setting time.
	maxTime = NumericProperty( pref.get('MaxTime', default=45) )
	timeStep = NumericProperty( pref.get('TimeStep', default=0.5) )
	heaterPeriod = pref.get( 'HeaterPeriod', default=30 )
	totalCount = NumericProperty( pref.get( 'TotalCount', default=0 ) )
	heaterP = pref.get( 'HeaterP', default=30 ) # PID proportional value.
	heaterI = pref.get( 'HeaterI', default=1 ) 	# PID integral value.
	heaterIBand = pref.get( 'HeaterIBand', default=20 ) # Integral Band value.
	setptStep = pref.get( 'SetPtStep', default=50 ) # Step change to adjust setpt.
	tempOKBand = pref.get( 'TempOKBand', default=10 ) # Temp OK band around setpt.
	openDelay = pref.get( 'MoldOpenDelay', default=1. ) # Min mold hold open delay.
	cnt = 0
	chatterLockout = False	# Keeps the relay from turning on again within one cycle.
	partDetLatch = False

	arburgModes = [ "Init", "Abort", "Auto", "Auto2", "Auto_Stop", "Manual" ]
	arburgStates = [ "Idle", "Close", "Inject", "Cool", "Open", "Eject", "Inject2", "Cool2", "Detect" ]
	arburgMode = "Init"		# Default Mode
	arburgState = "Idle"	# Default State
	arburgModeOld = ""		# Detects changes in Mode.
	arburgStateOld = ""		# Detects changes in State.
	temp = False
	#autoStop = False

	i = 0.


	# -------------------------------------------------------------------------
	def __init__(self, **kwargs):
		# Setup main timer to run 10 times per second.
		self.clock = Clock.schedule_interval( self.partDetTimer, 0.1 )
		self.clock = Clock.schedule_interval( self.opTimer, 0.1 )
		self.cycleEnable = False	# Track current cycle state.
		self.partCount = 0			# Counter number of parts made.
		self.heaterTm = 0			# Heater cycle time.
		self.tempCnt = 10			# On zero count, read temp sensor.
		super( MainWindow, self ).__init__(**kwargs)
		self.ids.cycTm.value = pref.get('CycleTm', default=20. )
		self.ids.injTm.value = pref.get('InjTm', default=10. )
		self.ids.partDbleEjectLbl.active = pref.get( 'DoubleEject', default=False)
		self.ids.partDbleInjectLbl.active = pref.get( 'DoubleInject', default=False)


	# This is the main Operations Timer for the whole system.
	# This should run at 10Hz.
	# -------------------------------------------------------------------------
	def opTimer( self, *largs ):

		self.refresh_task()

		self.updatePartDet()

		#self.heaterTimer()	# Handles Heater Band Stuff
		self.updateEStop()	# Read E-Stop button and update.
	 	# Update the time on the display.
	 	self.ids.timeLbl.text = strftime( "%l:%M:%S %P" )

		# Exit if mode is not in the list of acceptable modes.
		if self.arburgMode not in self.arburgModes:
			print "\n\n\rError: Unknown Mode ->", self.arburgMode
			print "Exiting App\n\r"
			App.get_running_app().stop()

		# The next block of code does all the mode switching logic.  Each modeXXX()
		# function is called once on switching to that new mode.

		# On Init mode, do init stuff then go to Manual mode.
		if (self.arburgMode == "Init") and (self.arburgMode != self.arburgModeOld):
			self.arburgModeOld = self.arburgMode
			self.modeInit()

		# Abort current cycle.
		if (self.arburgMode == "Abort") and (self.arburgMode != self.arburgModeOld):
			self.arburgModeOld = self.arburgMode
			self.modeAbort()

		# Run machine in Auto cycle.
		if (self.arburgMode == "Auto") and (self.arburgMode != self.arburgModeOld):
			self.arburgModeOld = self.arburgMode
			self.modeAuto()

		# Run machine in Auto two shot mode (injects a double shot).
		if (self.arburgMode == "Auto2") and (self.arburgMode != self.arburgModeOld):
			self.arburgModeOld = self.arburgMode
			self.modeAuto2()

		# Auto_Stop, finish this cycle then stop by going to manual.
		if (self.arburgMode == "Auto_Stop") and (self.arburgMode != self.arburgModeOld):
			self.arburgModeOld = self.arburgMode
			self.modeAutoStop()

		# Manual mode idles the machine and allows manual cycling things.
		if (self.arburgMode == "Manual") and (self.arburgMode != self.arburgModeOld):
			self.arburgModeOld = self.arburgMode
			self.modeManual()

		# The following functions are called at 10Hz rate based on the current mode.
		# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

		# If either Auto or Auto_Stop call self.auto().
		if self.arburgMode in ["Auto", "Auto_Stop"]:
			self.auto()

		if self.arburgMode == "Manual":
			self.manual()


	# This function handles Auto and Auto_Stop mode.  Call this function at 10Hz.
	# -------------------------------------------------------------------------
	def auto( self ):
		# If Idle, switch to Close state...
		if self.arburgState == "Idle":
			self.arburgState = "Close"
			self.timer = 0.
			self.cycleEnable = True
			#print "Auto: Idle to Close"
			close.on()
			inj.on()
			self.ids.closeSol.active = True
			self.ids.injSol.active = True
		# Else, for any of the following modes run the timer up.
		elif self.arburgState in [ "Close", "Inject", "Cool", "Eject", "Open", "Inject2", "Cool2" ]:
			self.timer += 0.1

		if self.arburgState == "Close":
			if self.timer >= self.ids.injTm.value:
				self.arburgState = "Cool"
				#print "Auto: Close to Cool"
				inj.off()
				self.ids.injSol.active = False

		if self.arburgState == "Cool":
			if self.timer >= self.ids.cycTm.value:
				self.arburgState = "Open"
				#print "Auto: Cool to Open"
				self.partDetLatch = False	# Clear the high speed part detect latch.
				close.off()
				self.ids.closeSol.active = False

		if self.arburgState == "Open":
			if self.timer >= self.ids.cycTm.value + self.openDelay:
				self.arburgState = "Eject"
				blowOff.on()
	 			self.partCount += 1
 				self.totalCount += 1
 				pref.update_preferences( { 'TotalCount': self.totalCount } )
	 			self.ids.partCount.text = str( self.partCount )

		if self.arburgState == "Eject":
			if self.ids.partDbleEjectLbl.active == True:
				# Crapy Double Pump during eject.
				# ------------------------------------------------------------
				# Time Values Were: 1.2, 2.2, 3.2 or 0.7, 1.5, 2.0
				if self.timer >= self.ids.cycTm.value + self.openDelay + 2.0:
					self.arburgState = "Detect"
				elif self.timer >= self.ids.cycTm.value + self.openDelay + 1.5:
					close.off()
				elif self.timer >= self.ids.cycTm.value + self.openDelay + 0.7:
					blowOff.off()
					close.on()
			else:
				# Normal Eject
				# ------------------------------------------------------------
				if self.timer >= self.ids.cycTm.value + self.openDelay + 0.2:
					blowOff.off()
				if self.timer >= self.ids.cycTm.value + self.openDelay + 0.4:
					self.arburgState = "Detect"

		if self.arburgState == "Detect":
			if self.arburgMode == "Auto_Stop":
				self.arburgMode = "Manual"
				#print "Auto_Stop: Detect to Manual/Idle"
			elif self.partDetLatch == True:
				self.arburgState = "Close"
				self.timer = 0.
				close.on()
				inj.on()
				self.ids.closeSol.active = True
				self.ids.injSol.active = True
				#print "Auto: Detect to Close"


	# This function handles Manual mode.  Call this function at 10Hz while in manual.
	# -------------------------------------------------------------------------
	def manual( self ):
		if self.ids.closeSol.active:
			close.on()
		else:
			close.off()

		if self.ids.injSol.active:
			inj.on()
		else:
			inj.off()



	# -------------------------------------------------------------------------
	def modeInit( self ):
		self.arburgMode = "Manual"	# Go from Init to Manual mode.
		#print "UPS Status OK: ", ups.is_pressed
		#print "Init"

	# -------------------------------------------------------------------------
	def modeAbort( self ):
		close.off()
		inj.off()
		self.ids.closeSol.active = False
		self.ids.injSol.active = False
		self.arburgState = "Idle"
		#print "Abort"

	# -------------------------------------------------------------------------
	def modeAuto( self ):
		self.arburgState = "Idle"	# Start auto mode in the idle state.
		#print "Auto"

	# -------------------------------------------------------------------------
	def modeAuto2( self ):
		pass
		#print "Auto2"

	# -------------------------------------------------------------------------
	def modeAutoStop( self ):
		pass
		#print "Auto_Stop"

	# On manual mode, make sure everything starts in the off position.
	# -------------------------------------------------------------------------
	def modeManual( self ):
		close.off()
		inj.off()
		self.ids.closeSol.active = False
		self.ids.injSol.active = False	
		self.autoStop = False
		#print "Manual"


	# Pool the part detect switch at 100Hz and latch true if detected.
	# -------------------------------------------------------------------------
	def partDetTimer( self, *largs ):
		if partDet.is_pressed == False:
			self.partDetLatch = True

	# -------------------------------------------------------------------------
	def updatePartDet( self ):
		if partDet.is_pressed == True:
			self.ids.partDetLbl.active = False
		else:
			self.ids.partDetLbl.active = True


	def refresh_task( self, *args ):
		s = "{:04.1f}".format( self.timer )		# Convert float to string like "12.3".
		self.ids.seg1.value = s[0]				# Assign first 7-segment to tens digit.
		self.ids.seg2.value = s[1:3]			# 2nd 7-segment gets ones digit, plus decimal point.
		self.ids.seg3.value = s[3]				# 3rd 7-segment gets tenths digit.
		#self.counts += self.rate
		#if self.counts >= 99.8: self.rate = -0.1
		#if self.counts <=  0.1: self.rate = 0.1



	# Call this often to handle the e-stop getting pressed.  Note, the e-stop
	# button also cuts 110vac to the mold close and inject solenoids.
	# -------------------------------------------------------------------------
	def updateEStop( self ):
		# E-Stop is active low...
		#if estop.is_pressed == False:
		if estop.is_pressed:
			# Unselect cycle button and depress abort button.  Then, disable 
			# both buttons until the e-stop is released.
			self.ids.cycleStart.state = 'normal'
			self.ids.abortCycle.disabled = True
			self.ids.abortCycle.state = 'down'
			self.ids.abortCycle.disabled = True
			self.ids.heaterEn.active = False

			# Make sure everything is aborted / off on e-stop pressed.
			self.ids.closeSol.active = False
			self.ids.injSol.active = False
			self.abortDisabled = True
			self.timer = 0.
			self.cycleEnable = False
			close.off()
			inj.off()
			heater.off()
			heater2.off()
			self.arburgMode = "Abort"
			self.arburgState = "Idle"
		else:
			self.ids.abortCycle.disabled = False		


	# Start a cycle on pressing this button.  Or, enter Auto_Stop if depressed.
	# -------------------------------------------------------------------------
	def enableStart( self, enState ):
		if enState == 'down':
			self.arburgMode = "Auto"
		else:
			self.arburgMode = "Auto_Stop"
			# autoStop disables the cycle-start button until the cycle completes.
			self.autoStop = True


		"""
		if enState == 'down':
			# if self.arburgState == 'Idle':
			#if self.cycleEnable == False:
			self.timer = 0.
			self.cycleEnable = True
			self.arburgState = 'Auto'
			print("Start Button")
		else:
			self.arburgState = 'Idle'
			#self.cycleEnable = False
		return True
		"""

	# On Abort Button active, disable the cycle start button.  Keep enable 
	# button disabled until abort button is released.
	# -------------------------------------------------------------------------
	def cycleAbort( self, abortState ):
		if abortState == 'down':
			self.ids.closeSol.active = False
			self.ids.injSol.active = False
			self.abortDisabled = True
			self.timer = 0.
			self.cycleEnable = False
			self.ids.cycleStart.state = 'normal'
			self.chatterLockout == False
			close.off()
			inj.off()
			blowOff.off()
			#print('Abort Button Down')
			self.arburgMode = "Abort"
			self.arburgState = "Idle"
		else:
			#print('Abort Button Up')
			self.abortDisabled = False
			self.arburgMode = "Manual"
			self.arburgState = "Idle"
			self.autoStop = False
		return True

	# Update the text over the slider for total cycle time.
	# -------------------------------------------------------------------------
	def cycleTmText( self, val ):
		val = self.ids.cycTm.value + self.openDelay
		if val > 0: 
			s = '{0:.1f}s ({1:.0f} Parts/Hr)'.format( val, 60*(60. / val) )
		else:
			s = "0"
		return s

	# Update the text over the slider for total cycle time.
	# -------------------------------------------------------------------------
	def injTmText( self, val ):
		if val > 0: 
			s = '{0:.1f}s'.format( val )
		else:
			s = "0"
		return s

	# Save all the settings to settings.py file.
	# -------------------------------------------------------------------------
	def saveSettings( self ):
		pref.update_preferences( { 'SetPt': self.tempSetPt } )
		pref.update_preferences( { 'CycleTm': self.ids.cycTm.value } )
		pref.update_preferences( { 'InjTm': self.ids.injTm.value } )
		pref.update_preferences( { 'HeaterPeriod': self.heaterPeriod } )
		pref.update_preferences( { 'TotalCount': self.totalCount } )
		pref.update_preferences( { 'MoldOpenDelay': self.openDelay } )
		pref.update_preferences( { 'DoubleEject': self.ids.partDbleEjectLbl.active})
		pref.update_preferences( { 'DoubleInject': self.ids.partDbleInjectLbl.active})

	# On "Close App" button...
	# -------------------------------------------------------------------------
	def closeApp( self ):
		App.get_running_app().stop()

	# -------------------------------------------------------------------------
	def chartTemp( self ):
		popup = Popup(title='Temperature Charting Popup',
		    content=Label(text='Future Feature - Maybe Someday...'),
		    size_hint=(None, None), size=(400, 400) )
		popup.open()

	# -------------------------------------------------------------------------
	def testCode( self ):
		#self.autoStop = True
		pass


# Used to test if a number is NaN (Not a Number).  The thermocouple lib 
# returns a NaN if the sensor is unplugged.
# -------------------------------------------------------------------------
def isNaN(num):
    return num != num


# Main Arburg app starts here.
# =============================================================================
class ArburgApp(App):
    def build(self):
        return MainWindow()


if __name__ == '__main__':
    ArburgApp().run()



	# -------------------------------------------------------------------------
	# def heaterTimer( self ):
	# 	# Read the thermocouple once per second.
	# 	self.tempCnt -= 1			# Down count to zero.
	# 	if self.tempCnt <= 0:		# On zero count... 
	# 		self.tempCnt = 10		# Reset counter to 10 for 10Hz down count.

	# 		tc = tempTC.readTempC()
	# 		if isNaN( tc ):
	# 			self.tempSensor = 0
	# 			#self.ids.tempLbl.text = "???"
	# 		else:
	# 			self.tempSensor = int( tc )
	# 			#self.ids.tempLbl.text = u"[b]{:d}\u00b0C".format( int(tc) )


	# 		# Set temp label color blue if too cold!
	# 		if self.tempSensor < ( self.tempSetPt - self.tempOKBand ):
	# 			self.tempLblColor = ( 0,0,1,1)
	# 		# Set temp label color red if too hot!
	# 		elif self.tempSensor > ( self.tempSetPt + self.tempOKBand ):
	# 			self.tempLblColor = ( 1,0,0,1)
	# 		# Else, set label color green if just right.
	# 		else:
	# 			self.tempLblColor = ( 0,1,0,1)

	# 		# Calculate 'self.heaterOut' based on actual temperature compared to
	# 		# the setpoint.  Call this at 1Hz.
	# 		self.heaterControl()

	# 	# Handle control of the heater band relay based on 'self.heaterOut'
	# 	# which is a percent of on time for a given period.  Call this at 10Hz.
	# 	self.heaterControlUpdate()



	# This function calculates the heater band output percent with a very crude
	# PID style.  Actually, this only calculates PI of PID.  The derivative term 
	# is not calculated.  This should be called at a 1Hz rate.
	# -------------------------------------------------------------------------
	# def heaterControl( self ):

	# 	# Calculate the error between SetPoint and Actual Temperature.  A 
	# 	# positive error means the temperature is low and we need more output.
	# 	err = self.tempSetPt - self.tempSensor
		
	# 	# Only update the output percent if control is "Auto".
	# 	if self.ids.heaterEn.active == True:
	# 		# Example, if heaterP equaled 2 and err equaled 25 degrees, the
	# 		# proportional part of the output would be 2 * 25, or 50% out.
	# 		# That gets added to the integral part.
	# 		p = self.heaterP * err 						# Calc P of PID

	# 		# Only integrate if output is not saturated.
	# 		if (self.heaterOut < 100.) and (self.heaterOut > 0.):
	# 			# Only integrate if error is within a limited bounds.
	# 			if abs( err ) < self.heaterIBand:
	# 				self.i = self.i + self.heaterI * err 	# Calc I of PID
	# 		# Else, on saturated output.
	# 		else:
	# 			# Drive the integral value toward zero.  This should help 
	# 			# prevent integral windup.
	# 			if self.i > 0.:
	# 				self.i -= self.heaterI * err
	# 			else:
	# 				self.i += self.heaterI * err

	# 		# Combine P and I parts of PID.
	# 		out = p + self.i 	

	# 		# Clamp the calculated output to zero to 100% output.
	# 		if out >= 100.: out = 100.
	# 		if out <= 0.0: out = 0.

	# 		# # Update actual output value with calculated value.
	# 		# step = 5.0		# Max step per update.  Keeps jumps from happening.
	# 		# if self.heaterOut < out:
	# 		# 	if self.heaterOut <= (100. - step):
	# 		# 		self.heaterOut += step
	# 		# if self.heaterOut > out:
	# 		# 	if self.heaterOut >= step:
	# 		# 		self.heaterOut -= step

	# 		self.heaterOut = out

	# 	# Else, if auto mode is off...
	# 	else:
	# 		self.i = 0.		# reset the integral term to zero.		

	# Heater Band Temperature Control - Call this function at 10Hz rate.
	# The heater is controlled by a relay that is on for a percentage of a 
	# total period value.  The relay is turned on and off based on a duty 
	# cycle and period value.  Example, on for 15 seconds out of 30 seconds 
	# for 50% output.  Period would be 30s and duty would be 15s.
	# -------------------------------------------------------------------------
	# def heaterControlUpdate( self ):
	# 	# Auto / Manual switch...
	# 	if self.ids.heaterEn.active == True:
	# 		# Counts up at 10Hz rate.  So, counting to 10s takes 100 counts.
	# 		self.heaterTm += 1

	# 		# Duty Cycle time in terms of 10Hz count rate.
	# 		onDuty = ( self.heaterOut / 10.) * self.heaterPeriod
	# 		# Period in terms of 10Hz counts.
	# 		period = self.heaterPeriod * 10

	# 		# If current timer value is less than the duty output value...
	# 		if self.heaterTm <= onDuty and self.chatterLockout == False:
	# 			# Turn on the heater.
	# 			self.chatterLockout = True 			# Only once per cycle.
	# 			self.ids.heaterOut.active = True
	# 			heater.on()
	# 			heater2.on()
	# 		elif self.heaterTm > onDuty and self.chatterLockout == True:
	# 			# Else, turn off the heater for the remainder of the period. 
	# 			self.ids.heaterOut.active = False
	# 			heater.off()
	# 			heater2.off()

	# 		# Recycle counter to zero after counting up to period seconds count.
	# 		if self.heaterTm >= period:
	# 			self.chatterLockout = False
	# 			self.heaterTm = 0
	# 	# Else, heater output is disabled so just turn everything off.
	# 	else:
	# 		self.heaterTm = 0
	# 		self.ids.heaterOut.active = False
	# 		heater.off()
	# 		heater2.off()



	# # Callback to adjust temperature setpoint up.
	# # -------------------------------------------------------------------------
	# def adjTempUp( self ):
	# 	self.tempSetPt += self.setptStep
	# 	return True

	# # Callback to adjust temperature setpoint down.
	# # -------------------------------------------------------------------------
	# def adjTempDown( self ):
	# 	self.tempSetPt -= self.setptStep
	# 	return True

	# # Switch control over man/auto control of the heater band.
	# # -------------------------------------------------------------------------
	# def heaterManControl( self, value ):
	# 	#print('Heater Manual Enable:{}'.format(value.active))
	# 	return True

	# # -------------------------------------------------------------------------
	# def closeSol( self, value ):
	# 	if value.active == True:
	# 		#close.on()
	# 		pass
	# 	else:
	# 		#close.off()
	# 		pass
	# 	return True

	# # -------------------------------------------------------------------------
	# def injSol( self, value ):
	# 	if value.active == True:
	# 		pass
	# 		#inj.on()
	# 	else:
	# 		#inj.off()
	# 		pass
	# 	return True




	# -------------------------------------------------------------------------
	#def on_partDet( self, val ):
	#	print "New Part", val

	# # -------------------------------------------------------------------------
	# def mainTimer( self, *largs ):

	# 	# Check hardware e-stop.  On e-stop, turn everything off.
	# 	self.updateEStop()

	# 	# Update the time on the display.
	# 	self.ids.timeLbl.text = strftime( "%l:%M:%S %P" )

	# 	if self.partDetLatch:			# Gets set true in the 100Hz timer.
	# 		self.ids.partDetLbl.active = True
	# 		if self.cycleEnable == False and self.arburgState == 'Auto':
	# 			self.timer = 0.
	# 			self.cycleEnable = True
	# 	# If not pressed, reset the GUI and the latch.
	# 	if partDet.is_pressed == False:
	# 		self.ids.partDetLbl.active = False
	# 		self.partDetLatch = False

	# 	# Read the thermocouple once per second.
	# 	self.tempCnt -= 1			# Down count to zero.
	# 	if self.tempCnt <= 0:		# On zero count... 
	# 		self.tempCnt = 10		# Reset counter to 10 for 10Hz down count.
	# 		self.tempSensor = int( tempTC.readTempC() )		# Read thermocouple.

	# 		# Set temp label color blue if too cold!
	# 		if self.tempSensor < ( self.tempSetPt - self.tempOKBand ):
	# 			self.tempLblColor = ( 0,0,1,1)
	# 		# Set temp label color red if too hot!
	# 		elif self.tempSensor > ( self.tempSetPt + self.tempOKBand ):
	# 			self.tempLblColor = ( 1,0,0,1)
	# 		# Else, set label color green if just right.
	# 		else:
	# 			self.tempLblColor = ( 0,1,0,1)

	# 		# Calculate 'self.heaterOut' based on actual temperature compared to
	# 		# the setpoint.  Call this at 1Hz.
	# 		self.heaterControl()

	# 	# Handle control of the heater band relay based on 'self.heaterOut'
	# 	# which is a percent of on time for a given period.  Call this at 10Hz.
	# 	self.heaterControlUpdate()

	# 	# Turn on injection solenoid until timeout and update label.
	# 	if self.cycleEnable:
	# 		if self.timer <= self.ids.injTm.value:
	# 			self.ids.injSol.active = True
	# 		else:
	# 			self.ids.injSol.active = False

	# 	"""
	# 	if self.timer <= self.ids.injTm.value:
	# 		if self.cycleEnable:
	# 			if self.arburgMode == 'Auto':
	# 				self.ids.injSol.active = True
	# 				inj.on()
	# 				self.arburgMode = 'Inj'
	# 				print "Inj"
	# 	elif self.cycleEnable:
	# 		if self.arburgMode == 'Inj':
	# 			self.ids.injSol.active = False
	# 			inj.off()
	# 			self.arburgMode = 'Cool'
	# 			print "Cool"
	# 	"""
		
	# 	if self.cycleEnable:
	# 		# Update cycle time label while enabled.
	# 		self.timer += 0.1	# Accumulate time in the timer.
	# 		self.ids.cycTmLbl.text = '{0:.1f}s'.format( self.timer )

	# 		self.ids.closeSol.active = True

	# 	# Stop cycle on timer finishing.
	# 	if self.timer >= self.ids.cycTm.value:
	# 		close.off()
	# 		if self.cycleEnable:
	# 			self.cycleEnable = False
	# 			self.ids.closeSol.active = False
	# 			self.ids.injSol.active = False
	# 			self.partCount += 1
	# 			self.totalCount += 1
	# 			pref.update_preferences( { 'TotalCount': self.totalCount } )
	# 			self.ids.partCount.text = str( self.partCount )
	# 			self.ids.cycTmLbl.text = '{0:.1f}s'.format( self.ids.cycTm.value )
	# 			self.arburgMode = 'Auto'
	# 	else:
	# 		if self.cycleEnable:
	# 			close.on()
