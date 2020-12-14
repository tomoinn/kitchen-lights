# Kitchen Lights

This is the code for my WS2812b based kitchen lighting. It uses a Hue to MQTT bridge
(which can be at found https://github.com/dale3h/hue-mqtt-bridge) to bridge from a 
Hue dimmer switch to a raspberry pi running the Python code here. The code allows for
animated routines or static colours, and handles fading between multiple animated or
static routines as well as advanced colour management to make use of the RGBW LEDs in
the strips I'm using.