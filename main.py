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
is_receiving = True  # Global flag to control reception

# Mutex for serial port access
port_lock = threading.Lock()


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

                # Вызов обновления статуса после отправки данных
                update_status()
        except serial.SerialException as e:
            output_widget.insert(tk.END, f"Error opening port {port}: {str(e)}\n")
            output_widget.see(tk.END)
            print(f"Error opening port {port}: {str(e)}")  # More detailed console output


def receive(port, output_widget, baudrate):
    global byte_count_rx1, byte_count_rx2, is_receiving  # Объявляем глобальные переменные

    print(f"Listening on {port}...")  # Отладочное сообщение
    try:
        with serial.Serial(port, baudrate) as ser:
            while is_receiving:  # Цикл продолжается, пока флаг True
                try:
                    data = ser.readline()  # Чтение данных из порта
                    if data:  # Проверяем, есть ли данные
                        print(f"Raw data received on {port}: {data}")  # Отладочное сообщение

                        # Увеличиваем счетчики байтов после успешного приема
                        if port == 'COM2':
                            byte_count_rx1 += len(data)
                        elif port == 'COM4':
                            byte_count_rx2 += len(data)

                        # Обновляем статус после приема данных
                        update_status()

                        # Выводим данные в соответствующее окно
                        output_widget.insert(tk.END, f"Received on {port}: {data.decode().strip()}\n")
                        output_widget.see(tk.END)

                except Exception as e:
                    print(f"Error while reading data on {port}: {str(e)}")  # Сообщение об ошибке чтения
    except serial.SerialException as e:
        print(f"Error opening port {port}: {str(e)}")  # Сообщение об ошибке открытия порта


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
    is_receiving = False  # Устанавливаем флаг в False


def start_communication(tx_data1, tx_data2):
    # Обнуляем счетчики перед отправкой данных
    global byte_count_tx1, byte_count_rx1, byte_count_tx2, byte_count_rx2
    byte_count_tx1 = 0
    byte_count_rx1 = 0
    byte_count_tx2 = 0
    byte_count_rx2 = 0

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
root.geometry("800x600")

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

# Baudrate settings frame
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
    entry.insert(0, str(baudrate[port]))  # Set default value
    baudrate_entries[port] = entry

# Confirm button for setting baudrates
confirm_button = ttk.Button(baudrate_frame, text="Set Baudrates", command=set_baudrates)
confirm_button.pack(pady=5)

# Stop receiving button
stop_button = ttk.Button(root, text="Stop Receiving", command=stop_receiving)
stop_button.grid(row=3, column=0, padx=10, pady=10)

# Start receiving threads on initialization
start_receiving()

# Update status at the beginning
update_status()

root.mainloop()