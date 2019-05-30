#!/usr/bin/python

#################################
# WSTK_railtest_range_test.py
# v1.0 - 2018-11-01 - kris.young@silabs.com
#################################
# (C) Copyright 2018 Silicon Labs, http://www.silabs.com</b>
#################################
# This file is licensed under the Silabs License Agreement. See the file
# "Silabs_License_Agreement.txt" for details. Before using this software for
# any purpose, you must agree to the terms of that agreement.
#################################

# This is a test script that uses the CLI on RAILtest to send messages
# between two ethernet connected WSTK nodes.

import telnetlib
import serial
import multiprocessing
import time

# TODO: Use argparse to supply these as command line arguments
tx_node_ip = "192.168.1.122"
tx_node_name = "[TX]" # for debug printing
rx_node_ip = "192.168.1.151"
rx_node_name = "[RX]" # for debug printing
iterations = 100
channel = "15"
tx_power_decidbm = "100" # 10 dBm
debug_print = False # True for verbose CLI messages (useful for debugging)

#This is just a unique pattern that we can filter for to reject real network packets
packet_string = "0x0f 0xde 0xad 0xbe 0xef 0xde 0xad 0xbe 0xef 0xde 0xad 0xbe 0xef 0xa5"

prompt_string = ">" # railtest prompt is ">" character

#Space out the packets to give the CLI time to print the packets. This could
# probably be optimized for test duration
tx_delay_ms = "50"

def init_node (wstk_ip, nodename):

    tempserial = telnetlib.Telnet(wstk_ip, 4901, 5)
    management = telnetlib.Telnet(wstk_ip, 4902, 5)

    # Reset the target
    management.read_until("WSTK>")
    management.write("target reset 3A000108\r\n")


    #init node using railtest CLI - generic for both RX and TX
    out_string = nodename + " INIT! WSTK IP address: " + wstk_ip
    out_string = out_string + tempserial.read_until(prompt_string)
    time.sleep(1) # Compensate for some startup delay in RAILTest CLI
    tempserial.write("rx 0\r\n") # enter idle mode
    out_string = out_string + tempserial.read_until(prompt_string)
    tempserial.write("setchannel " + channel + "\r\n")
    out_string = out_string + tempserial.read_until(prompt_string)
    if debug_print == True:
        print out_string
        print nodename + " END INIT"

    return tempserial

txserial = init_node(tx_node_ip, tx_node_name)
rxserial = init_node(rx_node_ip, rx_node_name)

# This is the thread for tx
# Send outbound packets and notify inbound thread when done
def tx_thread():
    errors = 0
    successes = 0.0 # defined as float for division result
    rssi_vals = []

    # Set up TX specific stuff
    txserial.write("setpower " + tx_power_decidbm + "\r\n")
    resp = tx_node_name + txserial.read_until(prompt_string)
    txserial.write("settxdelay " + tx_delay_ms + "\r\n") # set tx delay
    resp = resp + tx_node_name + txserial.read_until(prompt_string)
    txserial.write("settxpayload 0 " + packet_string + "\r\n") # set tx payload
    resp = resp + tx_node_name + txserial.read_until(prompt_string)
    txserial.write("tx " + str(iterations) + "\r\n") # start tx
    resp = resp + tx_node_name + txserial.read_until(prompt_string)
    while 1:
        exp = txserial.expect(["(txEnd)"],1) #nonblock, 1 sec timeout
        resp = resp + exp[2]
        if exp[0] != -1:
            break
    if debug_print == True:
        print(resp)
    if "error" in resp:
        errors += 1

    # Tell RX node that we're done with TX
    done_queue.put('DONE')
    if debug_print == True:
        print(tx_node_name + " TOTAL TX: {}".format(iterations))
        print(tx_node_name + " TOTAL ERRORS: {}".format(errors))


# This is the TX thread
# Log any received packets, stop when message received from TX thread
def rx_thread():

    errors = 0
    successes = 0.0 # defined as float for division result
    rssi_vals = []

    rxserial.write("rx 1\r\n") # start rx
    resp = rx_node_name + rxserial.read_until(prompt_string)
    if debug_print == True:
        print(resp)

    while 1:
        # Wait for data received from other node
        resp = rxserial.expect([packet_string],1) #nonblock, 1 sec timeout
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

    print("PACKETS RX: {}".format(int(successes)))
    print("PACKETS TX: {}".format(iterations))
    print("PER: {0:.0%}".format(1 - (successes/iterations)))
    if len(rssi_vals) != 0:
        print("RSSI (AVG:MAX:MIN) dBm: {}:{}:{}".format(sum(rssi_vals)/len(rssi_vals), max(rssi_vals), min(rssi_vals)))
    print("\r\n")

# Set up the threads
if __name__ == '__main__':
    tx_process = multiprocessing.Process(name='n1_process', target=tx_thread)
    rx_process = multiprocessing.Process(name='n2_process', target=rx_thread)
    done_queue = multiprocessing.Queue() #queue from TX task to RX task
    tx_process.start()
    rx_process.start()
