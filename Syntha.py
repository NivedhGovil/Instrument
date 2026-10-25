# ESP32 Touch Synthesizer 

import network
import socket
import time
from machine import Pin, PWM

# -------------------- WIFI ACCESS POINT --------------------
ap = network.WLAN(network.AP_IF)
ap.active(True)
ap.config(essid="ESP32_Music_Box", password="password123")
print("Wi-Fi network: ESP32_Music_Box")
print("Wi-Fi password: password123")
print("Open this address in your phone browser:", ap.ifconfig()[0])

# -------------------- GPIO SETUP --------------------
# Touch inputs (HW-138) — HIGH when touched
touch_inputs = [
    Pin(15, Pin.IN),
    Pin(32, Pin.IN),
    Pin(33, Pin.IN),
    Pin(18, Pin.IN),
]

# LEDs (with 220 Ω resistors)
led_outputs = [
    Pin(19, Pin.OUT),
    Pin(21, Pin.OUT),
    Pin(22, Pin.OUT),
    Pin(23, Pin.OUT),
]

# Power switch on GPIO 4 (internal pull-up)
# Closed to GND = ON (reads 0)
power_switch = Pin(4, Pin.IN, Pin.PULL_UP)

# Passive buzzer on GPIO 25 (PWM for different notes)
buzzer = PWM(Pin(25), freq=1000, duty=0)

# -------------------- MUSIC SETTINGS --------------------
# Notes: C, D, E, G
notes = [262, 294, 330, 392]
synth_on = (power_switch.value() == 0)

web_note_end_ms = 0
web_note_index = -1

# -------------------- BUZZER FUNCTIONS --------------------
def play_note(frequency):
    if not synth_on or frequency <= 0:
        buzzer.duty(0)
    else:
        buzzer.freq(frequency)
        buzzer.duty(512)

def stop_note():
    buzzer.duty(0)

def short_beep(frequency=800, duration_ms=100):
    if synth_on:
        buzzer.freq(frequency)
        buzzer.duty(512)
        time.sleep_ms(duration_ms)
        stop_note()

# -------------------- WEB PAGE --------------------
def web_page():
    status_text = "POWER OFF" if not synth_on else "POWER ON"
    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>ESP32 Synth Controller</title>
    <style>
        body {{ font-family: Arial, sans-serif; text-align: center; background: #20232a; color: white; margin: 20px; }}
        h1 {{ color: #7dd3fc; }}
        .status {{ font-size: 20px; margin: 20px; }}
        .btn {{ display: inline-block; font-size: 18px; padding: 14px 20px; margin: 7px; border: 0; border-radius: 9px; color: white; text-decoration: none; }}
        .note {{ background: #1677c8; }}
    </style>
</head>
<body>
    <h1>ESP32 Touch Synthesizer</h1>
    <p class="status">Status: <b>{status_text}</b></p>
    <p>Tap a note button to play it briefly.</p>
    <a class="btn note" href="/note0">Note 1 (C)</a>
    <a class="btn note" href="/note1">Note 2 (D)</a>
    <a class="btn note" href="/note2">Note 3 (E)</a>
    <a class="btn note" href="/note3">Note 4 (G)</a>
</body>
</html>"""

# -------------------- HTTP SERVER --------------------
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server.bind(("0.0.0.0", 80))
server.listen(3)
server.setblocking(False)

print("Synthesizer ready.")
print("Dashboard: http://192.168.4.1")

def handle_web_request():
    global web_note_end_ms, web_note_index
    try:
        conn, addr = server.accept()
    except OSError:
        return
    conn.setblocking(False)
    request = ""
    try:
        request = conn.recv(1024).decode("utf-8")
    except OSError:
        pass
    if request:
        if synth_on and "GET /note0 " in request:
            play_note(notes[0])
            web_note_index = 0
            web_note_end_ms = time.ticks_add(time.ticks_ms(), 300)
        elif synth_on and "GET /note1 " in request:
            play_note(notes[1])
            web_note_index = 1
            web_note_end_ms = time.ticks_add(time.ticks_ms(), 300)
        elif synth_on and "GET /note2 " in request:
            play_note(notes[2])
            web_note_index = 2
            web_note_end_ms = time.ticks_add(time.ticks_ms(), 300)
        elif synth_on and "GET /note3 " in request:
            play_note(notes[3])
            web_note_index = 3
            web_note_end_ms = time.ticks_add(time.ticks_ms(), 300)
    page = web_page()
    try:
        conn.send(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n")
        conn.sendall(page.encode("utf-8"))
    except OSError:
        pass
    conn.close()

# -------------------- MAIN LOOP --------------------
while True:
    handle_web_request()

    # Follow the power switch directly (LOW = ON)
    switch_is_on = (power_switch.value() == 0)
    if switch_is_on != synth_on:
        synth_on = switch_is_on
        stop_note()
        if not synth_on:
            for led in led_outputs:
                led.off()
        print("Synthesizer power:", "ON" if synth_on else "OFF")

    now = time.ticks_ms()

    # Stop web-triggered note when its time is up
    if web_note_index >= 0 and time.ticks_diff(now, web_note_end_ms) >= 0:
        web_note_index = -1
        web_note_end_ms = 0
        if not any(pin.value() for pin in touch_inputs):
            stop_note()

    if not synth_on:
        for led in led_outputs:
            led.off()
        stop_note()
    else:
        any_touch = False
        for index in range(4):
            touched = touch_inputs[index].value() == 1
            if touched:
                led_outputs[index].on()
                any_touch = True
                if web_note_index < 0:
                    play_note(notes[index])
            else:
                led_outputs[index].off()
        if not any_touch and web_note_index < 0:
            stop_note()

    time.sleep_ms(10)