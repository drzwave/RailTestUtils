#!/usr/bin/python

#################################
# WSTK_railtest_ZWave_range_test.py
#
# This program sends FrameCount (default=100) frames from one Ethernet connected WSTK to another.
# Each WSTK must have the RailTest binary download into the Z-Wave chip
#
# V2.0 - 2019-05-28 - DrZWave@silabs.com - copied Kris version and modified for ZWave
# v1.0 - 2018-11-01 - kris.young@silabs.com
#################################
# Copyright 2019 Silicon Labs, http://www.silabs.com</b>
#################################
# This file is licensed under the Silabs License Agreement. See the file
# "Silabs_License_Agreement.txt" for details. Before using this software for
# any purpose, you must agree to the terms of that agreement.
#################################

# This is a test script that uses the CLI on RAILtest to send Z-Wave frames
# between two ethernet connected WSTK nodes.

import telnetlib
import serial
import time
import threading

# TODO: supply these as command line arguments
tx_node_ip = "192.168.7.95"
tx_node_name = b"[TX]" # for debug printing
rx_node_ip = "192.168.7.94"
rx_node_name = b"[RX]" # for debug printing
FrameCount = b'100'

# Region: 0=EU, 1=US, 2=ANZ, 3=HK etc - See A=INS14283 700 series Bring-up/Test HW Development - section 4 for the full list
REGION = b"1"

TxPower = b"04" # Raw value from 0 to 110, 0=lowest power, 110=max power

Channel = b"0" # 0=110kbit, 1=40k, 2=9.6k

DEBUG = 5 # 0=debugging messages off, higher numbers print more messages

#This is just a unique pattern that we can filter for to reject real network packets
packet_string = b"0x0f 0x0e 0x11 0x22 0x33 0x44 0x55 0x14 0x77 0x88 0x99 0xaa 0xbb 0xcc" # TODO add 0xdd 0xee 0x10 0x11

prompt_string = b">" # railtest prompt is ">" character

#Space out the packets to give the CLI time to print the packets.
tx_delay_ms = b"100"

class ZWaveRangeTest():
    ''' Send FrameCount Z-Wave frames from TX_NODE_IP to RX_NODEIP '''
    def __init___(self):
        self.usage()

    def InitTx(TxIp):
        ''' Returns the TX handle after opening the Tx Telnet and initializing or None if it fails'''
        if DEBUG>5: print("START INIT TX:")
        try:
            txser = telnetlib.Telnet(TxIp, 4901, 5) # Telnet port to the RailTest CLI
        except:
            return(None)
        txser.write(b"rx 0\r\n") # enter idle mode - See INS14283 section 4.4.3 for the initialization sequence
        resp=txser.read_until(prompt_string,1) # capture the return data from the WSTK for debugging
        if DEBUG>9: print(resp) # capture the return data from the WSTK for debugging
        txser.write(b"SetZWaveMode 1 3\r\n")
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        txser.write(b"SetChannel " + Channel + b" \r\n")
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        txser.write(b"SetZWaveRegion " + REGION + b" \r\n")
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        time.sleep(.5)  # sometimes the WSTK needs a break otherwise it doesn't receive the entire command
        txser.write(b"SetTxPayload 7 20\r\n")
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        txser.write(b"SetTXLength 20\r\n")
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        txser.write(b"SetPower " + TxPower + b" raw\r\n")
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        txser.write(b"settxdelay " + tx_delay_ms +  b"\r\n") # set tx delay
        resp=txser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        if DEBUG>5: print("END INIT TX")
        return(txser)

    def InitRx(RxIp):
        ''' Returns the RX handle after opening the Tx Telnet and initializing or None if it fails'''
        if DEBUG>5: print("START INIT RX:")
        try:
            rxser = telnetlib.Telnet(RxIp, 4901, 5) # Telnet port to the RailTest CLI
        except:
            return(None)
        rxser.write(b"rx 0\r\n") # enter idle mode - See INS14283 section 4.4.3 for the initialization sequence
        resp=rxser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        rxser.write(b"SetZWaveMode 1 3\r\n")
        resp=rxser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        rxser.write(b"SetChannel " + Channel + b" \r\n")
        resp=rxser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        rxser.write(b"SetZWaveRegion " + REGION + b" \r\n")
        resp=rxser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        rxser.write(b"rx 1 \r\n")
        resp=rxser.read_until(prompt_string,1)
        if DEBUG>9: print(resp)
        if DEBUG>5: print('END INIT RX:')
        return(rxser)

    def TxSend(txser):
        ''' Send the TX frames '''
        errors=0
        time.sleep(3)   # wait for the RX to be ready - TODO could be a queue or semaphore but this is easy...
        if DEBUG>1: print("Begin Transmit")
        txser.write(b"tx " + FrameCount + b"\r\n") # start tx in 5s to give time for the RX to be ready
        resp = txser.read_until(prompt_string,1)
        while 1:
            exp = txser.expect([b"(txEnd)"],1) #nonblock, 1 sec timeout
            resp = resp + exp[2]
            if exp[0] != -1:
                break
            if b"error" in resp:
                errors += 1
                if DEBUG>3: print(exp)
        if DEBUG>5: print("TxSend done: errors={}".format(errors))

    def RxGet(rxser):
        ''' Receives the frames and returns the count of successfully received frames'''
        rssi_vals = []
        successes=0
        timeout=0
        while timeout<(int(FrameCount)*1.1 + 5) and successes<int(FrameCount):  # TODO - change this to a queue or handshake from the TX thread to end shortly after all frames have been transmitted.
            # Wait for data received from other node
            resp = rxser.expect([packet_string],1) #nonblock, 1 sec timeout
            if resp[0] != -1:
                successes = successes + 1
                rssival = resp[2].split(b'{rssi:',1)[1].split(b'}')[0]
                rssi_vals.append(int(rssival))
                if DEBUG>9: print("rssi={}".format(rssival))
            timeout+=1

        print("PACKETS TX: {}".format(int(FrameCount)))
        print("PACKETS RX: {}".format(successes))
        print("PER: {:.0%} at power {}".format(1 - (successes/int(FrameCount)),int(TxPower)))
        if len(rssi_vals) != 0:
            print("RSSI (AVG:MAX:MIN) dBm: {}:{}:{}".format(int(sum(rssi_vals)/len(rssi_vals)), max(rssi_vals), min(rssi_vals)))
        return(successes)
    
    def ResetWSTK(wstk_ip):
        ''' Reset the WSTK to be sure we're starting from a known point
            Returns an error code if failed and None if OK
        '''
        try:
            management = telnetlib.Telnet(wstk_ip, 4902, 5)
        except:
            return(-1)

        management.read_until(b'WSTK>',1)
        management.write(b"target reset 3A000108\r\n") # why the 3A000108?
        time.sleep(1) # wait for target to boot
        management.close()
        return(None)

    def usage():
        print("python WSTK_railtest_ZWaveRangeTest [options go here...]")
        print("Use the python -u option to see the print statements come out unbuffered which can help find timing problems")

if __name__ == '__main__':
    ''' Run the Z-Wave Range test '''

    # Reset both boards to start with a clean setup
    if ZWaveRangeTest.ResetWSTK(tx_node_ip) != None:
        print("failed to open Tx")
        exit()
    if ZWaveRangeTest.ResetWSTK(rx_node_ip) != None:
        print("failed to open Rx")
        exit()

    # open the telnet ports and initialize each WSTK
    txser=ZWaveRangeTest.InitTx(tx_node_ip)
    if txser == None: 
        print("failed to open TX Telnet")
        exit()
    rxser=ZWaveRangeTest.InitRx(rx_node_ip)
    if rxser == None: 
        print("failed to open RX Telnet")
        exit()

    # The RX is already running and ready to receive so start the transmit in its own thread so it can run in parallel
    txthread=threading.Thread(target=ZWaveRangeTest.TxSend(txser))

    ZWaveRangeTest.RxGet(rxser) # capture the RX frames and calculate the result

