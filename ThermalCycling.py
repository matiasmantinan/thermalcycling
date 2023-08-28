import datetime
import time
import serial
import os
import re
import subprocess
import sys
import socket

import argparse

from MPODControl.MPODControl import MPODControl
from HMPControl.HMPControlTools import * 
from Chiller.chiller_cf41 import *

import matplotlib.pyplot as plt
from scipy import stats
import numpy as np



HOT_TEMP = 40
COLD_TEMP = -45
CHILLER_TEMP = -25
HOT_TEMP_MAX = 60
COLD_TEMP_MAX = -55

file = open("ThermalData.txt","w")
file.write("Time[s]\tTemp[C]\tTchuck[C]\tDew Point[C]\tAir Humidity[%]\tPeltier Voltage[V]\tPeltier Current[A]\tPeltier Polarity\n")

BUFFER_SIZE = 1024
TCP_IP = '192.168.0.216'
TCP_PORT = 12400
s = socket.socket()
s.connect((TCP_IP, TCP_PORT))

peltier_polarity = 1 # 1 for cooling 0 for heating
test_finish = 0
out_msg = f"{peltier_polarity}\t{test_finish}"
s.send(out_msg.encode())


temps = []
times = []
chuck_temps = []
humidities = []
dew_points = []

startTime = time.time()

fig, ax = plt.subplots()
ax.set_xlabel("Time [s]")
ax.set_ylabel("Temperature [C]")


lastTemps = []
lastTimes = []
lastN = 10

# Just to check I will set the peltier Voltage to the max
Peltier_PS = connectRohdeS()    
Pltr_channel = 2
Pltr_voltage = 0.
Pltr_current = 8
    
setVoltCurr(Peltier_PS, Pltr_channel, Pltr_voltage, Pltr_current)  #device, channel no, voltage, current

peltier_on_off(Peltier_PS,Pltr_channel,1) #switch peltier ON = 1    

try:
    values=measVoltCurr(Peltier_PS, Pltr_channel) #measure voltage and current of channel Nch
    PL_voltage = round(float(values[0]), 2) #V
    PL_current = round(float(values[1]), 2) #A

    print(f"Peltier Voltage = {PL_voltage}\tPeltier Current={PL_current}")
except ValueError:
    print("Error reading voltage")


# returns peltie polarity, peltier voltage
def adjustPeltier(temp,slope,target,hot,peltier_polarity,peltier_voltage):
    PELTIER_MAX_VOLTAGE = 7. # 7 volts is the maximum voltage
    GROSS_ADJ_RANGE = 7 # gross adjustment range, within this range we control the voltage carefully but not too much
    MAX_SLOPE_GROSS = 7
    FINE_ADJ_RANGE = 3 # dine adjustment range, within this range we have to be carefull 
    MAX_SLOPE_FINE = 1
    MAX_SLOPE = 10

    FINE_INCREMENT = 0.01
    GROSS_INCREMENT = 0.02
    INCREMENT = .1
    
    DeltaT = temp - target

    if hot:
        peltier_polarity = 0
    else:
        peltier_polarity = 1

    #if abs(slope)>MAX_SLOPE:
    #    peltier_voltage -= INCREMENT
    #    return (peltier_polarity,peltier_voltage)


    if hot:
        if DeltaT<0:
            if -DeltaT>GROSS_ADJ_RANGE:
                if slope>MAX_SLOPE:
                    peltier_voltage -= INCREMENT
                else:
                    peltier_voltage += INCREMENT

            if -DeltaT>FINE_ADJ_RANGE:
                if slope>MAX_SLOPE_GROSS:
                    peltier_voltage -= GROSS_INCREMENT
                else:
                    peltier_voltage += GROSS_INCREMENT

            else:
                if slope>MAX_SLOPE_FINE:
                    peltier_voltage -= FINE_INCREMENT
                else:
                    peltier_voltage += FINE_INCREMENT

        if DeltaT>=0:
            if DeltaT>GROSS_ADJ_RANGE:
                if -slope>MAX_SLOPE:
                    peltier_voltage += INCREMENT
                else:
                    peltier_voltage -= INCREMENT

            if DeltaT>FINE_ADJ_RANGE:
                if -slope>MAX_SLOPE_GROSS:
                    peltier_voltage += GROSS_INCREMENT
                else:
                    peltier_voltage -= GROSS_INCREMENT

            else:
                if -slope>MAX_SLOPE_FINE:
                    peltier_voltage += FINE_INCREMENT
                else:
                    peltier_voltage -= FINE_INCREMENT
        
    if not hot:
        if DeltaT<0:
            if -DeltaT>GROSS_ADJ_RANGE:
                if slope>MAX_SLOPE:
                    peltier_voltage += INCREMENT
                else:
                    peltier_voltage -= INCREMENT

            if -DeltaT>FINE_ADJ_RANGE:
                if slope> MAX_SLOPE_GROSS:
                    peltier_voltage += GROSS_INCREMENT
                else:
                    peltier_voltage -= GROSS_INCREMENT

            else:
                if slope> MAX_SLOPE_FINE:
                    peltier_voltage += FINE_INCREMENT
                else:
                    peltier_voltage -= FINE_INCREMENT

        if DeltaT>=0:
            if DeltaT>GROSS_ADJ_RANGE:
                if -slope>MAX_SLOPE:
                    peltier_voltage -= INCREMENT
                else:
                    peltier_voltage += INCREMENT

            if DeltaT>FINE_ADJ_RANGE:
                if -slope>MAX_SLOPE_GROSS:
                    peltier_voltage-=GROSS_INCREMENT
                else:
                    peltier_voltage += GROSS_INCREMENT

            else:
                if -slope>MAX_SLOPE_FINE:
                    peltier_voltage -= FINE_INCREMENT
                else:
                    peltier_voltage += FINE_INCREMENT



    return (peltier_polarity,max(min(peltier_voltage,PELTIER_MAX_VOLTAGE),0.))

    
"""
def adjustPeltier(temp,slope,target,hot,peltier_polarity,peltier_voltage):
    PELTIER_MAX_VOLTAGE = 7. # 7 volts is the maximum voltage
    GROSS_ADJ_RANGE = 5 # gross adjustment range, within this range we control the voltage carefully but not too much
    MIN_SLOPE_GROSS = 3
    MAX_SLOPE_GROSS = 7
    FINE_ADJ_RANGE = 2 # dine adjustment range, within this range we have to be carefull 
    MAX_SLOPE_FINE = 1
    MAX_SLOPE = 13
    MIN_SLOPE = 10

    FINE_INCREMENT = 0.5
    GROSS_INCREMENT = 1
    INCREMENT = 2
    DeltaT = temp - target

    # peltier_voltage can never be 0
    if peltier_voltage < 0.1:
        peltier_voltage = 0.1


    if 0<DeltaT and peltier_polarity==1:
        if abs(DeltaT) < FINE_ADJ_RANGE:
            if slope>0:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
            elif abs(slope) > MAX_SLOPE_FINE:
                peltier_voltage = peltier_voltage*0.8
        elif abs(DeltaT) < GROSS_ADJ_RANGE:
            if slope >0:
                pass
            elif abs(slope) > MAX_SLOPE_GROSS:
                peltier_voltage = peltier_voltage*0.8
            elif abs(slope) < MIN_SLOPE_GROSS:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
        else:
            if slope>0:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
            elif abs(slope) > MAX_SLOPE:
                peltier_voltage = peltier_voltage*0.8
            elif abs(slope) < MIN_SLOPE:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)
            
    elif 0<DeltaT and peltier_polarity == 0:
        peltier_polarity = 1 # cool

    elif 0 >= DeltaT and peltier_polarity == 0:
        if abs(DeltaT) < FINE_ADJ_RANGE:
            if slope<0:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
            elif abs(slope) > MAX_SLOPE_FINE:
                peltier_voltage = peltier_voltage*0.8
        elif abs(DeltaT) < GROSS_ADJ_RANGE:
            if slope<0:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
            elif abs(slope) > MAX_SLOPE_GROSS:
                peltier_voltage = peltier_voltage*0.8
            elif abs(slope) < MIN_SLOPE_GROSS:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
        else:    
            if slope<0:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)        
            elif abs(slope) > MAX_SLOPE:
                peltier_voltage = peltier_voltage*0.8
            elif abs(slope) < MIN_SLOPE:
                peltier_voltage = min(peltier_voltage*1.2,PELTIER_MAX_VOLTAGE)

    elif 0 >= DeltaT and peltier_polarity == 1:
        peltier_polarity = 0 # heat



    return (peltier_polarity,peltier_voltage)

"""


cycle = 0

try:
    while not test_finish:
        
        if cycle == 4:
            HOT = True
            TARGET_TEMP = HOT_TEMP_MAX - 2
        elif cycle ==5:
            HOT = True
            TARGET_TEMP = HOT_TEMP_MAX
        elif cycle == 6:
            HOT = False
            TARGET_TEMP = COLD_TEMP_MAX +2
        elif cycle == 7:
            HOT = False
            TARGET_TEMP = COLD_TEMP_MAX
        elif cycle == 8:
            test_finish = True
        elif cycle%6 == 0:
            HOT = True
            TARGET_TEMP = HOT_TEMP-2
        elif cycle%6 == 1:
            HOT = True
            TARGET_TEMP = HOT_TEMP
        elif cycle%6 == 2:
            HOT = False
            TARGET_TEMP = COLD_TEMP+2
        elif cycle%6 == 3:
            HOT = False
            TARGET_TEMP = COLD_TEMP


        try:
            in_msg = s.recv(BUFFER_SIZE).decode().split()
            
            temp = float(in_msg[0])
            tchuck = float(in_msg[1])
            air_humid = float(in_msg[2])
            dew_pt = float(in_msg[3])
            temps.append(temp)
            #chuck_temps.append(tchuck)
            #humidities.append(air_humid)
            #dew_points.append(dew_pt)

            t = (time.time()-startTime)
            times.append(t)
            #file.write("Time[s]\tTemp[C]\tTchuck[C]\tDew Point[C]\tAir Humidity[%]\tPeltier Voltage[V]\tPeltier Current[A]\tPeltier Polarity\n")
            file.write(f"{t}\t{temp}\t{tchuck}\t{dew_pt}\t{air_humid}\t{Pltr_voltage}\t{Pltr_current}\t{peltier_polarity}\n")

            if lastN>0:
                lastTemps.append(temp)
                lastTimes.append(t)

                #lastTemps.append(float(in_msg))
                #lastTimes.append(t)
                lastN-=1

                try:
                    values=measVoltCurr(Peltier_PS, Pltr_channel) #measure voltage and current of channel Nch
                    PL_voltage = round(float(values[0]), 2) #V
                    PL_current = round(float(values[1]), 2) #A

                except serial.serialutil.SerialException:
                    time.sleep(0.01)
                    continue
            
                ax.plot(times,temps,'r.')

            else:
                lastTemps = lastTemps[1:]+[temp]
                lastTimes = lastTimes[1:]+[t]

                linear_fit = stats.linregress(lastTimes,lastTemps)
                print("Time[s]\tTemp[C]\tTchuck[C]\tDew Point[C]\tAir Humidity[%]\tPeltier Voltage[V]\tPeltier Current[A]\tPeltier Polarity\tSlope[C/min]\tTarget Temp[C]\n")
                print(f"{t}\t{temp}\t{tchuck}\t{dew_pt}\t{air_humid}\t{Pltr_voltage}\t{Pltr_current}\t{peltier_polarity}\t{linear_fit.slope*60}\t{TARGET_TEMP}\n")

                try:
                    values=measVoltCurr(Peltier_PS, Pltr_channel) #measure voltage and current of channel Nch
                    PL_voltage = round(float(values[0]), 2) #V
                    PL_current = round(float(values[1]), 2) #A

                except serial.serialutil.SerialException:
                    time.sleep(0.01)
                    continue

                plt.cla()
                ax.plot(times,temps,'r.')
                ax.plot(lastTimes,lastTemps,'b.')
                ax.plot(lastTimes,linear_fit.intercept + np.array(lastTimes)*linear_fit.slope,'b')


                peltier_polarity,Pltr_voltage = adjustPeltier(temp,linear_fit.slope*60,TARGET_TEMP,HOT,peltier_polarity,Pltr_voltage)
                setVoltCurr(Peltier_PS, Pltr_channel, Pltr_voltage, Pltr_current)  #device, channel no, voltage, current

                # add peltier volt to 0 in between cycles here and higher the windows range
                if cycle%4 == 0:
                    if max([abs(x - TARGET_TEMP) for x in temps[-100:]]) < 1.5:
                        cycle+=1
                elif cycle%4 == 1:
                    if max([abs(x - TARGET_TEMP) for x in temps[-300:]]) < 1.5:
                        cycle+=1
                elif cycle%4 == 2:
                    if max([abs(x - TARGET_TEMP) for x in temps[-100:]]) < 1.5:
                        cycle+=1
                elif cycle%4 == 3:
                    if max([abs(x - TARGET_TEMP) for x in temps[-300:]]) < 1.5:
                        cycle+=1
        
        except ValueError:
            print("Error converting string to float")
        plt.pause(0.1)



        out_msg = f"{peltier_polarity}\t{test_finish}"
        # try adding encode 
        s.send(out_msg.encode())

except KeyboardInterrupt:
    peltier_on_off(Peltier_PS,Pltr_channel,0) #switch peltier OFF = 0
    file.close()



plt.show()