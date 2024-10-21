import serial
import threading
import tkinter as tk
from tkinter import ttk
import time
import random


ports = ['COM1', 'COM2', 'COM3', 'COM4']
n = 30
data_length = n + 1


baudrate = {port: 9600 for port in ports}


byte_count_tx1 = 0
byte_count_rx1 = 0
byte_count_tx2 = 0
byte_count_rx2 = 0
is_receiving = True


port_lock = threading.Lock()


class Frame:
    def __init__(self, source_address, data):
        self.flag = bin(n)[2:].zfill(8)
        self.destination_address = '0000'
        self.source_address = bin(int(source_address[-1]))[2:].zfill(4)


        self.data = data.ljust(data_length - 1, '0')

        self.hamming_code = self.generate_hamming_code(self.data)
        self.fcs = self.hamming_code

        self.stuffed_data, self.stuffed_bit_position = self.perform_bit_stuffing(self.data)

    def generate_hamming_code(self, data):

        data_bits = list(map(int, data))
        m = len(data_bits)
        r = 0

        while (2 ** r) < (m + r + 1):
            r += 1

        hamming_code = [0] * (m + r)

        j = 0
        for i in range(1, m + r + 1):
            if i == (2 ** j):
                j += 1
            else:
                hamming_code[i - 1] = data_bits[i - j - 1]

        for i in range(r):
            parity_position = 2 ** i
            parity_value = 0
            for k in range(1, m + r + 1):
                if k & parity_position:
                    parity_value ^= hamming_code[k - 1]
            hamming_code[parity_position - 1] = parity_value

        print(f"Generated Hamming Code: {''.join(map(str, hamming_code))}")

        return ''.join(map(str, hamming_code))

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

def corrupt_data(data):

    data_bits = list(data)


    if random.random() < 0.6:
        index = random.randint(0, len(data_bits) - 1)
        data_bits[index] = '1' if data_bits[index] == '0' else '0'

    if random.random() < 0.25:
        indices = random.sample(range(len(data_bits)), 2)
        for index in indices:
            data_bits[index] = '1' if data_bits[index] == '0' else '0'

    return ''.join(data_bits)


def transmit(port, data, baudrate):
    global byte_count_tx1, byte_count_tx2
    frame = Frame(port, data)
    frame_string = frame.to_string() + "\n"

    corrupted_data = frame.data
    frame_with_correction = Frame(port, corrupted_data)
    corrupted_frame_string = frame_with_correction.to_string() + "\n"

    print(f"Transmitting on {port}: {corrupted_frame_string.strip()}")

    if port == 'COM1':
        output_text1.insert(tk.END, f"Transmitting on {port}: {corrupted_frame_string.strip()}\n")
    elif port == 'COM3':
        output_text2.insert(tk.END, f"Transmitting on {port}: {corrupted_frame_string.strip()}\n")

    with port_lock:
        try:
            with serial.Serial(port, baudrate) as ser:
                ser.write(corrupted_frame_string.encode())
                if port == 'COM1':
                    byte_count_tx1 += len(corrupted_frame_string.encode())
                elif port == 'COM3':
                    byte_count_tx2 += len(corrupted_frame_string.encode())

                update_status()
        except serial.SerialException as e:
            print(f"Error opening port {port}: {str(e)}")


def decode_hamming_code(received_data):
    received_bits = list(map(int, received_data))
    m = len(received_bits)
    r = 0

    while (2 ** r) < (m + 1):
        r += 1

    error_position = 0
    for i in range(r):
        parity_position = 2 ** i
        parity_value = 0
        for j in range(1, m + 1):
            if j & parity_position:
                parity_value ^= received_bits[j - 1]
        if parity_value != 0:
            error_position += parity_position

    if error_position:
        received_bits[error_position - 1] ^= 1

    data_bits = []
    j = 0
    for i in range(m):
        if (i + 1) != (2 ** j):
            data_bits.append(received_bits[i])
        else:
            j += 1


    decoded_data = ''.join(map(str, data_bits)).rstrip('0')
    print(f"Decoded Data after extraction: {decoded_data}")

    return decoded_data

def receive(port, output_widget, baudrate):
    global byte_count_rx1, byte_count_rx2, is_receiving

    print(f"Listening on {port}...")
    try:
        with serial.Serial(port, baudrate) as ser:
            while is_receiving:
                try:
                    data = ser.readline()
                    if data:
                        print(f"Raw data received on {port}: {data}")

                        if port == 'COM2':
                            byte_count_rx1 += len(data)
                        elif port == 'COM4':
                            byte_count_rx2 += len(data)

                        received_frame = data.decode().strip()
                        print(f"Received Frame: {received_frame}")


                        fcs_received = received_frame.split(', ')[-1].split(': ')[1]
                        data_received = decode_hamming_code(fcs_received)

                        output_widget.insert(tk.END, f"Received on {port}: {received_frame}\n")
                        output_widget.see(tk.END)

                        print(f"Decoded Data: {data_received}")

                except Exception as e:
                    print(f"Error while reading data on {port}: {str(e)}")
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


def set_baudrates():
    global baudrate
    for port in ports:
        try:
            new_baudrate = int(baudrate_entries[port].get())
            baudrate[port] = new_baudrate
            print(f"Baudrate set to {new_baudrate} for {port}.")
        except ValueError:
            print(f"Invalid baudrate value for {port}.")


def start_receiving():
    threading.Thread(target=receive, args=('COM2', output_text1, baudrate['COM2']), daemon=True).start()
    threading.Thread(target=receive, args=('COM4', output_text2, baudrate['COM4']), daemon=True).start()


def stop_receiving():
    global is_receiving
    is_receiving = False


def start_communication(tx_data1, tx_data2):
    global byte_count_tx1, byte_count_rx1, byte_count_tx2, byte_count_rx2
    byte_count_tx1 = 0
    byte_count_rx1 = 0
    byte_count_tx2 = 0
    byte_count_rx2 = 0

    if tx_data1:
        threading.Thread(target=transmit, args=('COM1', tx_data1, baudrate['COM1'])).start()
        time.sleep(0.1)
    if tx_data2:
        threading.Thread(target=transmit, args=('COM3', tx_data2, baudrate['COM3'])).start()
        time.sleep(0.1)


def is_binary_string(s):
    return all(char in '01' for char in s)


def convert_input_to_binary(input_data):
    binary_data = ""
    for line in input_data:
        if line:
            for char in line:
                if char in '01':
                    binary_data += char
                else:
                    binary_data += format(ord(char), '08b')
    return binary_data


def send_data1():
    tx_data1 = input_text1.get("1.0", tk.END).strip().splitlines()
    for line in tx_data1:
        binary_data = convert_input_to_binary([line])
        if binary_data:
            start_communication(binary_data, "")


def send_data2():
    tx_data2 = input_text2.get("1.0", tk.END).strip().splitlines()
    for line in tx_data2:
        binary_data = convert_input_to_binary([line])
        if binary_data:
            start_communication("", binary_data)


root = tk.Tk()
root.title("Serial Communication Interface")
root.geometry("800x600")


input_frame1 = ttk.LabelFrame(root, text="Send Port: COM1")
input_frame1.grid(row=0, column=0, padx=10, pady=10)
input_text1 = tk.Text(input_frame1, height=5, width=30)
input_text1.grid(row=0, column=0, padx=5, pady=5)
send_button1 = ttk.Button(input_frame1, text="Send", command=send_data1)
send_button1.grid(row=1, column=0, padx=5, pady=5)


output_frame1 = ttk.LabelFrame(root, text="Receive Port: COM2")
output_frame1.grid(row=1, column=0, padx=10, pady=10)
output_text1 = tk.Text(output_frame1, height=10, width=30)
output_text1.grid(row=0, column=0, padx=5, pady=5)


input_frame2 = ttk.LabelFrame(root, text="Send Port: COM3")
input_frame2.grid(row=0, column=1, padx=10, pady=10)
input_text2 = tk.Text(input_frame2, height=5, width=30)
input_text2.grid(row=0, column=0, padx=5, pady=5)
send_button2 = ttk.Button(input_frame2, text="Send", command=send_data2)
send_button2.grid(row=1, column=0, padx=5, pady=5)


output_frame2 = ttk.LabelFrame(root, text="Receive Port: COM4")
output_frame2.grid(row=1, column=1, padx=10, pady=10)
output_text2 = tk.Text(output_frame2, height=10, width=30)
output_text2.grid(row=0, column=0, padx=5, pady=5)


status_frame = ttk.LabelFrame(root, text="Status")
status_frame.grid(row=2, column=0, padx=10, pady=10)

status_label = ttk.Label(status_frame, text="", justify=tk.LEFT)
status_label.grid(row=0, column=0, padx=5, pady=5)


baudrate_frame = ttk.LabelFrame(root, text="Set Baudrates")
baudrate_frame.grid(row=2, column=1, padx=10, pady=10)

baudrate_entries = {}
for port in ports:
    row = ttk.Frame(baudrate_frame)
    row.pack(pady=5)

    label = ttk.Label(row, text=f"{port}:")
    label.pack(side=tk.LEFT)

    entry = ttk.Entry(row, width=8)
    entry.pack(side=tk.LEFT)
    entry.insert(0, str(baudrate[port]))
    baudrate_entries[port] = entry


confirm_button = ttk.Button(baudrate_frame, text="Set Baudrates", command=set_baudrates)
confirm_button.pack(pady=5)

start_receiving()
update_status()

root.mainloop()