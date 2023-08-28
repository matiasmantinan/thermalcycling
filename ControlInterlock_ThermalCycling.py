from influxdb import InfluxDBClient
import datetime
import time
import serial
import os
import re
import subprocess
import sys
import socket

from MPODControl.MPODControl import MPODControl
from HMPControl.HMPControlTools import * 
from Chiller.chiller_cf41 import *
from Alarmer import *
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--powerSwitch', '-p', action='store_true', default=False, help='power switch ON if this is Ture')
parser.add_argument('--HVSwitch', action='store_true', default=False, help='HV power switch ON if this is Ture')
parser.add_argument('--LVSwitch', action='store_true', default=False, help='LV power switch ON if this is Ture')
args = parser.parse_args()


def read_info(tevent, temperature, air_humid, tchuck, temperature_moduleN, dew_pt, IsPressure, IsVac, IsLidClosed, IsOkay):
    teventdate, teventtime = tevent.split("-")
    data_list = [{
        'measurement': 'RD53A-001-RealModule',
        'tags': {'cpu': 'ITkTestSetupA'},
        'fields':{
            'time': teventtime, #datetime.datetime.now().strftime("%H:%M:%S"),
            'temperature': float(temperature),
            'air_humid': float(air_humid),
            'temperature_chuck' : float(tchuck),
            'temperature_moduleN' : float(temperature_moduleN),
            'dew_pt': float(dew_pt),
            'is_presOK': int(IsPressure),
            'is_vacOK': int(IsVac),
            'is_lidClosed' : int(IsLidClosed),
            'is_okay' : int(IsOkay)
        }
    }]
    return data_list

def read_IV_info(HV_voltage, HV_current, LV_voltage, LV_current, PL_voltage, PL_current):
    
    data_list = [{
        'measurement': 'RD53A-001-RealModule',
        'tags': {'cpu': 'ITkTestSetupA'},
        'fields':{
            'time': datetime.datetime.now().strftime("%H:%M:%S"),
            'HV_voltage': float(HV_voltage),
            'HV_current': float(HV_current),
            'LV_voltage': float(LV_voltage),
            'LV_current': float(LV_current),
            'PL_voltage': float(PL_voltage),
            'PL_current': float(PL_current)
        }                                                          
    }]
    return data_list

client = InfluxDBClient(host='localhost',port=8086)
#client.create_database('dcsDB')
client.switch_database('dcsDB')

#initiate Chiller
ser = initiate_chiller()

s = socket.socket()
host = '192.168.0.216'
port = 12399
s.connect((host, port))

powerSwitch = args.powerSwitch #set to 1 if want to switch on chiller and Power Supplyies
inst_start_count = 0
PelVolt_steps = 0
run_once = 1
stop_once = 1
temp_value = -25 # chiller temp
reach_temperature = -25 #check this value for each run

ps_peltier = connectRohdeS()    

Nch_pltr = 2
Pltr_voltage = 2 
Pltr_current = 8
setVoltCurr(ps_peltier, Nch_pltr, Pltr_voltage, Pltr_current)  #device, channel no, voltage, current
    
mpod = MPODControl()
channel_LV = 0
LV_voltage = 2.1
LV_current = 5.88
channel_HV = 311
HV_voltage = 0
HV_current = 0
mpod.set_voltageCurrent(channel_LV,LV_voltage,LV_current)
mpod.set_voltageCurrent(channel_HV,HV_voltage,HV_current)
mtemp = 1000.

try:
    print("Setting temperature")
    set_temp(ser, temp_value)
    time.sleep(5)
    print("Switching chiller ON")
    chiller_on(ser)
    time.sleep(10)

    fname_IntState = time.strftime("InterlockStatusData/InterlockStatusData_%Y%m%d%H%M%S.txt")
    fInterlock=open(fname_IntState, "a+")
    fInterlock.write(f"EventTime\taTemp\tRH\tDP\tcTemp\tmTemp\tHV\tHV_I\tLV\tLV_I\tPlV\tPl_I\tsLid\tsVac\tsPressure\tIsOkay\n")
    fInterlock.close()
    print(f"EventTime\taTemp\tRH\tDP\tcTemp\tmTemp\tHV\tHV_I\tLV\tLV_I\tPlV\tPl_I\tsLid\tsVac\tsPressure\tIsOkay\n")
    
    while True:
        try:
            string = s.recv(1024).decode()
        except:
            print("bad string")
        #print(string)

        try:
            try:
                LV_voltage = mpod.read_senseVoltage(channel_LV) #V
                LV_current = (mpod.read_measCurrent(channel_LV)) #mA
                HV_voltage = mpod.read_senseVoltage(channel_HV) #V
                HV_current = (mpod.read_measCurrent(channel_HV))*1E6 #uA
                
                values=measVoltCurr(ps_peltier, Nch_pltr) #measure voltage and current of channel Nch
                PL_voltage = round(float(values[0]), 2) #V
                PL_current = round(float(values[1]), 2) #A

            except serial.serialutil.SerialException:
                time.sleep(0.01)
                continue


            if len(string.split())!=10: continue
            tevent, temperature, air_humid, dew_pt, tchuck, temperature_moduleN, IsLidClosed, IsVac, IsPressure, IsOkay = string.split()
            AllOkay = int(IsOkay)
            mtemp = temperature_moduleN

            delta_ModuleTemp = abs(float(temperature_moduleN)-reach_temperature)
            if run_once == 1:
                # if |T_module - T_reach|<5 and everything is okay, starat to count 100 then turn on LV,HV, and peltier
                if delta_ModuleTemp < 10 and AllOkay:   #change to 1 fro actual program  
                    inst_start_count += 1
                    if inst_start_count == 10:
                        print("Switching ON Peltier")
                        peltier_on_off(ps_peltier,Nch_pltr,1) #switch peltier ON = 1    
                if delta_ModuleTemp < 2 and AllOkay:   #change to 1 fro actual program  
                    if inst_start_count == 100:
                        if powerSwitch == 1: # need to be set to 1 in the begining of code
                            #time.sleep(10)
                            mpod.channel_switch(channel_LV,args.LVSwitch)   #switch LV MPOD ON = 1  
                            mpod.channel_switch(channel_HV,args.HVSwitch)   #switch HV MPOD ON = 1
                            run_once = 0

            # if |T_module - T_reach|>2 .. FIXME
            if delta_ModuleTemp > 2:
                if PelVolt_steps > 100 and PelVolt_steps%50 == 0 and Pltr_voltage <= 0.5: # DY
                    setVolt(ps_peltier, Nch_pltr, Pltr_voltage)
                    Pltr_voltage += 0.5
                PelVolt_steps += 1

            # stop all instruments when AllOkay become false for the first time
            if AllOkay == 0:
                if stop_once == 1:
                    print("Interlock Triggered: Switching OFF HV, LV, Peltier, and Chiller")
                    mpod.channel_switch(channel_HV,0)   #switch HV MPOD OFF = 0
                    mpod.channel_switch(channel_LV,0)   #switch LV MPOD OFF = 0
                    peltier_on_off(ps_peltier,Nch_pltr,0) #switch peltier OFF = 0
                    chiller_off(ser)
                    stop_once = 0

            client.write_points(read_info(tevent, temperature, air_humid, tchuck, temperature_moduleN, dew_pt, IsPressure, IsVac, IsLidClosed, IsOkay))
            client.write_points(read_IV_info(HV_voltage, HV_current, LV_voltage, LV_current, PL_voltage, PL_current))
            print(f"{tevent}\t{temperature}\t{air_humid}\t{dew_pt}\t{tchuck}\t{temperature_moduleN}\t{HV_voltage}\t{HV_current}\t{LV_voltage}\t{LV_current}\t{PL_voltage}\t{PL_current}\t{IsLidClosed}\t{IsVac}\t{IsPressure}\t{IsOkay}\n")
            fInterlock=open(fname_IntState, "a+")
            fInterlock.write(f"{tevent}\t{temperature}\t{air_humid}\t{dew_pt}\t{tchuck}\t{temperature_moduleN}\t{HV_voltage}\t{HV_current}\t{LV_voltage}\t{LV_current}\t{PL_voltage}\t{PL_current}\t{IsLidClosed}\t{IsVac}\t{IsPressure}\t{IsOkay}\n")
            fInterlock.close()
        except ValueError:
            print("Oooops! Raspi issue, not getting all numbers. Try again ...")

except (KeyboardInterrupt, SystemExit): #when you press ctrl+c
    print("Killing Thread... Switching OFF HV, LV, Peltier, and Chiller")
    mpod.channel_switch(channel_HV,0)   #switch HV MPOD OFF = 0
    mpod.channel_switch(channel_LV,0)   #switch LV MPOD OFF = 0
    peltier_on_off(ps_peltier,Nch_pltr,0) #switch peltier OFF = 0
    chiller_off(ser)
    if float(mtemp) < 10: print("\033[91mMODULE TEMPERATURE (%sC) IS TOO LOW. LAB DEW POINT IS 10C. DO NOT OPEN THE BOX YET!!\033[0m"%(mtemp))

