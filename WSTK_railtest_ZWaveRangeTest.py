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
import multiprocessing
import time

# TODO: Use argparse to supply these as command line arguments
tx_node_ip = "192.168.7.95"
tx_node_name = b"[TX]" # for debug printing
rx_node_ip = "192.168.7.94"
rx_node_name = b"[RX]" # for debug printing
FrameCount = b'2'

# Region: 0=EU, 1=US, 2=ANZ, 3=HK etc - See A=INS14283 700 series Bring-up/Test HW Development - section 4 for the full list
REGION = b"1"

TxPower = b"50" # Raw value from 0 to 110, 0=lowest power, 110=max power

Channel = b"0" # 0=110kbit, 1=40k, 2=9.6k

debug_print = True # True for verbose CLI messages (useful for debugging)

#This is just a unique pattern that we can filter for to reject real network packets
packet_string = b"0x0f 0x0e 0x11 0x22 0x33 0x44 0x55 0x66 0x77 0x88 0x99 0xaa 0xbb 0xcc" # TODO add 0xdd 0xee 0x10 0x11

prompt_string = b">" # railtest prompt is ">" character

#Space out the packets to give the CLI time to print the packets. This could
# probably be optimized for test duration
tx_delay_ms = b"50"

def init_node (wstk_ip, nodename):

    print (nodename + b" START INIT")
    tempserial = telnetlib.Telnet(wstk_ip, 4901, 5) # Telnet port to the RailTest CLI
    print ("@1",end="")
    management = telnetlib.Telnet(wstk_ip, 4902, 5)
    print ("@2",end="")

    # Reset the target - restart Railtest from the beginning
    management.read_until(b'WSTK>',1)
    print ("@3",end="")
    management.write(b"target reset 3A000108\r\n")
    time.sleep(1) # wait for target to boot
    management.close()
    print ("@4",end="")


    #init node using railtest CLI - generic for both RX and TX
    out_string = (nodename + b" INIT! WSTK IP address: " + wstk_ip.encode('ascii'))
    print ("@5",end="")
    out_string = out_string + tempserial.read_until(prompt_string,1)
    print ("@6",end="")
    tempserial.write(b"rx 0\r\n") # enter idle mode - See INS14283 section 4.4.3 for the initialization sequence
    print ("@7",end="")
    out_string = out_string + tempserial.read_until(prompt_string,1)
    tempserial.write(b"SetZWaveMode 1 3\r\n")
    out_string = out_string + tempserial.read_until(prompt_string,1)
    print ("@8",end="")
    tempserial.write(b"SetChannel " + Channel + b" \r\n")
    out_string = out_string + tempserial.read_until(prompt_string,1)
    print ("@9")
    tempserial.write(b"SetZWaveRegion " + REGION + b" \r\n")
    out_string = out_string + tempserial.read_until(prompt_string,1)
    print ("@10")
    if debug_print == True:
        print(out_string)
        print(nodename + b" END INIT")

    return tempserial

txserial = init_node(tx_node_ip, tx_node_name)
rxserial = init_node(rx_node_ip, rx_node_name)
done_queue = multiprocessing.Queue() #queue from TX task to RX task

# This is the thread for tx
# Send outbound packets and notify inbound thread when done
def tx_thread():
    errors = 0
    successes = 0.0 # defined as float for division result
    rssi_vals = []

    # Set up TX specific stuff
    txserial.write(b"SetTxPayload 7 20\r\n")
    resp = tx_node_name + txserial.read_until(prompt_string,1)
    txserial.write(b"SetTXLength 20\r\n")
    resp = tx_node_name + txserial.read_until(prompt_string,1)
    txserial.write(b"SetPower " + TxPower + b" raw\r\n")
    resp = tx_node_name + txserial.read_until(prompt_string,1)
    txserial.write(b"settxdelay " + tx_delay_ms +  b"\r\n") # set tx delay
    resp = resp + tx_node_name + txserial.read_until(prompt_string,1)
    txserial.write(b"tx " + FrameCount + b"\r\n") # start tx
    resp = resp + tx_node_name + txserial.read_until(prompt_string,1)
    while 1:
        exp = txserial.expect([b"(txEnd)"],1) #nonblock, 1 sec timeout
        resp = resp + exp[2]
        if exp[0] != -1:
            break
    if debug_print == True:
        print(resp)
    if b"error" in resp:
        errors += 1

    # Tell RX node that we're done with TX
    #done_queue.put('DONE')
    if debug_print == True:
        print("{} TOTAL TX: {}".format(tx_node_name, FrameCount))
        print("{} TOTAL ERRORS: {}".format(tx_node_name, errors))


# This is the RX thread
# Log any received packets, stop when message received from TX thread
def rx_thread():

    errors = 0
    successes = 0.0 # defined as float for division result
    rssi_vals = []

    rxserial.write(b"rx 0\r\n")
    resp = rx_node_name + rxserial.read_until(prompt_string,1)
    print(resp)
    rxserial.write(b"SetTxLength 60\r\n")
    resp = rx_node_name + rxserial.read_until(prompt_string,1)
    print(resp)
    rxserial.write(b"SetTxPayload 7 60\r\n")
    resp = rx_node_name + rxserial.read_until(prompt_string,1)
    print(resp)
    # Doesn't seem to need to add the channel hopping stuff...
    rxserial.write(b"rx 1\r\n") # start rx
    resp = rx_node_name + rxserial.read_until(prompt_string,1)
    print(resp)
    print("###########Here###########")
    if debug_print == True:
        print(resp)

    timeout=0
    while timeout<(int(FrameCount)*1.5 + 10):
        # Wait for data received from other node
        print("#1")
        #resp = rxserial.expect([packet_string],1) #nonblock, 1 sec timeout
        resp = rxserial.read_lazy()
        print("#2 {}.".format(resp))
        time.sleep(1)
        '''
        if resp[0] != -1:
            successes = successes + 1
            rssival = resp[2].split('{rssi:',1)[1].split('}')[0]
            rssi_vals.append(int(rssival))
            if debug_print == True:
                print(rx_node_name + " Packet received!")
                print("RSSI = " + rssival)
        else:
            try:
                if done_queue.get(False,1) == 'DONE': #nonblock, 1 sec timeout
                    break
            except:
                pass # No-op (but error not thrown)
        '''
        timeout+=1

    print("PACKETS RX: {}".format(int(successes)))
    print("PACKETS RX: {}".format(FrameCount))
    print("PER: {0:.0%}".format(1 - (successes/int(FrameCount))))
    if len(rssi_vals) != 0:
        print("RSSI (AVG:MAX:MIN) dBm: {}:{}:{}".format(sum(rssi_vals)/len(rssi_vals), max(rssi_vals), min(rssi_vals)))
    print("\r\n")

# Set up the threads
if __name__ == '__main__':
    print("Init RX_PROCESS")
    rx_process = multiprocessing.Process(name='RX_process', target=rx_thread)
    print("Init TX_PROCESS")
    tx_process = multiprocessing.Process(name='TX_process', target=tx_thread)
    time.sleep(5)
    print("Start RX_PROCESS")
    rx_process.start()
    time.sleep(5)
    print("Start TX_PROCESS")
    tx_process.start()

