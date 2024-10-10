import serial
import threading
import tkinter as tk
from tkinter import ttk
import time

# Define ports
ports = ['COM1', 'COM2', 'COM3', 'COM4']
n = 30  # Group number
data_length = n + 1  # Length of the data field

# Baudrate settings
baudrate = {port: 9600 for port in ports}

# Global variables for byte counts
byte_count_tx1 = 0
byte_count_rx1 = 0
byte_count_tx2 = 0
byte_count_rx2 = 0

# Mutex for serial port access
port_lock = threading.Lock()

# Hamming encoding function
def hamming_encode(data):
    n = len(data)
    r = 0
    while (2 ** r) < (n + r + 1):
        r += 1

    codeword = ['0'] * (n + r)

    j = 0
    for i in range(1, n + r + 1):
        if i == 2 ** j:
            j += 1
        else:
            codeword[i - 1] = data[i - j - 1]

    for i in range(r):
        parity_position = 2 ** i
        parity = 0
        for j in range(1, n + r + 1):
            if j & parity_position == parity_position:
                parity ^= int(codeword[j - 1])
        codeword[parity_position - 1] = str(parity)

    return ''.join(codeword)

# Frame structure class
class Frame:
    def __init__(self, source_address, data):
        self.flag = bin(n)[2:].zfill(8)  # Binary flag
        self.destination_address = '0000'  # Zero address
        self.source_address = bin(int(source_address[-1]))[2:].zfill(4)
        self.data = data.ljust(data_length, '0')

        # Data encoding and bit stuffing
        self.stuffed_data, self.stuffed_bit_position = self.perform_bit_stuffing(self.data)
        self.fcs = '00000000'  # Zero FCS

    def perform_bit_stuffing(self, data):
        stuffed_data = ""
        count = 0
        stuffed_bit_position = None  # To store the position of the stuffed bit
        for bit in data:
            if bit == '1':
                count += 1
                stuffed_data += '1'
                if count == 5:
                    stuffed_data += '0'
                    stuffed_bit_position = len(stuffed_data) - 1  # Position of stuffed bit
                    count = 0
            else:
                count = 0
                stuffed_data += '0'
        return stuffed_data, stuffed_bit_position

    def to_string(self):
        # Highlight the stuffed bit in the Data field
        data_display = list(self.data)
        if self.stuffed_bit_position is not None:
            data_display[self.stuffed_bit_position] = f"[{data_display[self.stuffed_bit_position]}]"
        data_string = ''.join(data_display)

        return (
            f"Flag: {self.flag}, "
            f"Dest Addr: {self.destination_address}, "
            f"Source Addr: {self.source_address}, "
            f"Data: {data_string}, "
            f"FCS: {self.fcs}"
        )

def transmit(port, data, baudrate):
    global byte_count_tx1, byte_count_tx2
    frame = Frame(port, data)  # Create frame
    frame_string = frame.to_string() + "\n"

    output_widget = output_text1 if port == 'COM1' else output_text2

    output_widget.insert(tk.END, f"Transmitting on {port}: {frame_string.strip()}")
    output_widget.see(tk.END)

    print(f"Transmitting on {port}: {frame_string.strip()}")  # Console output

    with port_lock:  # Ensure exclusive access to the serial port
        try:
            with serial.Serial(port, baudrate) as ser:
                ser.write(frame_string.encode())
                if port == 'COM1':
                    byte_count_tx1 += len(frame_string.encode())
                elif port == 'COM3':
                    byte_count_tx2 += len(frame_string.encode())
        except serial.SerialException as e:
            output_widget.insert(tk.END, f"Error opening port {port}: {str(e)}\n")
            output_widget.see(tk.END)
            print(f"Error opening port {port}: {str(e)}")  # More detailed console output

    update_status()

def receive(port, output_widget, baudrate):
    global byte_count_rx1, byte_count_rx2  # Declare global variables

    with port_lock:  # Ensure exclusive access to the serial port
        try:
            with serial.Serial(port, baudrate) as ser:
                while True:
                    data = ser.readline()
                    try:
                        decoded_data = data.decode().strip()
                        fcs_start = decoded_data.find("FCS:")
                        if fcs_start != -1:
                            print(f"Received on {port}: {decoded_data}")  # Console output

                            # Uncomment this line to display in GUI (if needed)
                            # output_widget.insert(tk.END, f"Received on {port}: {decoded_data}\n")
                            # output_widget.see(tk.END)

                            # Count received bytes
                            if port == 'COM2':
                                byte_count_rx1 += len(data)
                            elif port == 'COM4':
                                byte_count_rx2 += len(data)

                            update_status()
                    except UnicodeDecodeError:
                        pass  # Ignore incorrect data
        except serial.SerialException as e:
            print(f"Error opening port {port}: {str(e)}")

def update_status():
    status_label.config(
        text=(
            f"--- Status ---\n"
            f"TX Port 1: COM1\n"
            f"Bytes Sent: {byte_count_tx1}\n"
            f"RX Port 1: COM2\n"
            f"Bytes Received: {byte_count_rx1}\n\n"
            f"TX Port 2: COM3\n"
            f"Bytes Sent: {byte_count_tx2}\n"
            f"RX Port 2: COM4\n"
            f"Bytes Received: {byte_count_rx2}"
        )
    )

def start_receiving():
    threading.Thread(target=receive, args=('COM2', output_text1, baudrate['COM2']), daemon=True).start()
    threading.Thread(target=receive, args=('COM4', output_text2, baudrate['COM4']), daemon=True).start()

def start_communication(tx_data1, tx_data2):
    if tx_data1:
        threading.Thread(target=transmit, args=('COM1', tx_data1, baudrate['COM1'])).start()
        time.sleep(0.1)  # Delay before sending the next packet
    if tx_data2:
        threading.Thread(target=transmit, args=('COM3', tx_data2, baudrate['COM3'])).start()
        time.sleep(0.1)  # Delay before sending the next packet

def is_binary_string(s):
    return all(char in '01' for char in s)

def convert_input_to_binary(input_data):
    binary_data = ""
    for line in input_data:
        if line:  # Check for empty line
            for char in line:
                if char in '01':  # Check if the character is binary
                    binary_data += char  # Append directly if it's binary
                else:
                    binary_data += format(ord(char), '08b')  # Convert to binary
    return binary_data

def send_data1():
    tx_data1 = input_text1.get("1.0", tk.END).strip().splitlines()
    for line in tx_data1:  # Iterate over each line
        binary_data = convert_input_to_binary([line])  # Convert each line to binary
        if binary_data:  # Check for non-empty string
            start_communication(binary_data, "")

def send_data2():
    tx_data2 = input_text2.get("1.0", tk.END).strip().splitlines()
    for line in tx_data2:  # Iterate over each line
        binary_data = convert_input_to_binary([line])  # Convert each line to binary
        if binary_data:  # Check for non-empty string
            start_communication("", binary_data)

# Create main window
root = tk.Tk()
root.title("Serial Communication Interface")
root.geometry("700x600")

# Input window 1
input_frame1 = ttk.LabelFrame(root, text="Send Port: COM1")
input_frame1.grid(row=0, column=0, padx=10, pady=10)
input_text1 = tk.Text(input_frame1, height=5, width=30)
input_text1.grid(row=0, column=0, padx=5, pady=5)
send_button1 = ttk.Button(input_frame1, text="Send", command=send_data1)
send_button1.grid(row=1, column=0, padx=5, pady=5)

# Output window 1
output_frame1 = ttk.LabelFrame(root, text="Receive Port: COM2")
output_frame1.grid(row=1, column=0, padx=10, pady=10)
output_text1 = tk.Text(output_frame1, height=10, width=30)
output_text1.grid(row=0, column=0, padx=5, pady=5)

# Input window 2
input_frame2 = ttk.LabelFrame(root, text="Send Port: COM3")
input_frame2.grid(row=0, column=1, padx=10, pady=10)
input_text2 = tk.Text(input_frame2, height=5, width=30)
input_text2.grid(row=0, column=0, padx=5, pady=5)
send_button2 = ttk.Button(input_frame2, text="Send", command=send_data2)
send_button2.grid(row=1, column=0, padx=5, pady=5)

# Output window 2
output_frame2 = ttk.LabelFrame(root, text="Receive Port: COM4")
output_frame2.grid(row=1, column=1, padx=10, pady=10)
output_text2 = tk.Text(output_frame2, height=10, width=30)
output_text2.grid(row=0, column=0, padx=5, pady=5)

# Status window
status_frame = ttk.LabelFrame(root, text="Status")
status_frame.grid(row=2, column=0, padx=10, pady=10)

status_label = ttk.Label(status_frame, text="", justify=tk.LEFT)
status_label.grid(row=0, column=0, padx=5, pady=5)

# Start receiving threads on initialization
start_receiving()

# Update status at the beginning
update_status()

root.mainloop()