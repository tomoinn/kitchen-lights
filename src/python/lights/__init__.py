#! /home/pi/venv/bin/python
try:
    import board
    import neopixel
except NotImplementedError:
    board = None
    neopixel = None
import logging
import uuid
from abc import ABC, abstractmethod
from random import random, randint
from time import time, sleep
from typing import List

import paho.mqtt.client as mqtt

from lights.colour import RGBWColour, RGBW

NUM_PIXELS = 300

logger = logging.getLogger(name='lights')


class Routine(ABC):
    """
    Superclass of routines which can be stateful and which provide a method to
    evaluate their current state as an array of RGBW
    """

    @abstractmethod
    def get_rgbw_array(self, colour_model) -> List[RGBW]:
        pass


class Rainbows(Routine):
    """
    Routine which shows a looping smooth rainbow
    """

    def __init__(self, white_value=0.3, num_pixels=NUM_PIXELS):
        self.offset = 0
        self.white_value = white_value
        self._n = num_pixels

    def get_rgbw_array(self, colour_model):
        self.offset = (self.offset + 1) % self._n
        return [colour_model.hsv_to_rgbw(hue=4 * ((i + self.offset) % self._n) / self._n, sat=1.0, value=1.0,
                                         white=self.white_value)
                for i in range(self._n)]


class Sparkle(Routine):
    """
    Routine which shows sparkles of a range of hues, each of which gradually fades to the background
    level. Multiple new sparks are created each time the routine is resolved, and brightness values are
    smeared across adjacent pixels, allowing the spark to fade and spread over time.
    """

    def __init__(self, base_hue=0.55, hue_range=0.05, new_sparks=5, fade_factor=0.98):
        """
        :param base_hue:
            Centre hue for randomly assigned hue values
        :param hue_range:
            Maximum deviation above or below the centre point
        :param new_sparks:
            Number of new sparks added each iteration
        :param fade_factor:
            Factor by which all brightness values are multiplied each iteration
        """
        self.base_hue = base_hue
        self.hue_range = hue_range
        self._p = [(self.random_colour(), 0) for _ in range(NUM_PIXELS)]
        self.new_sparks = new_sparks
        self.fade_factor = fade_factor

    def random_colour(self):
        return self.base_hue + (random() * 2.0 - 1.0) * self.hue_range

    def smear_brightness(self, pixel):
        a, b, c = [self._p[(pixel + i) % NUM_PIXELS] for i in range(-1, 2)]
        return b[0], (a[1] + b[1] * 2 + c[1]) / 4

    def get_rgbw_array(self, colour_model):
        # Fade everything a bit
        self._p = list([(h, b * self.fade_factor) for h, b in self._p])
        # Smear brightness values
        self._p = [self.smear_brightness(i) for i in range(NUM_PIXELS)]
        for _ in range(self.new_sparks):
            self._p[randint(0, NUM_PIXELS - 1)] = self.random_colour(), 1.0
        return [colour_model.hsv_to_rgbw(h, 1.0, b, white=0.4 * b) for h, b in self._p]


class Lights:

    def __init__(self, colour_model=RGBWColour(), n=NUM_PIXELS, fade_duration=1):
        """
        :param colour_model:
            an instance of RGBWColour to manage gamma etc
        :param n:
            number of LEDs in the associated hardware
        :param fade_duration:
            time in seconds over which to fade in a newly assigned routine
        """
        self._n = n
        if neopixel:
            self._pixels = neopixel.NeoPixel(pin=board.D18,
                                             n=self._n,
                                             pixel_order=neopixel.GRBW,
                                             auto_write=False)
        else:
            logger.info('No neopixel driver available, proceeding in dummy mode')
        self._colour_model = colour_model
        self._routines = {}
        self._active_routine = None
        # fade time in seconds
        self._fade_duration = fade_duration
        self._last_fade_time = time()

    def _fade_routines(self):
        now = time()
        # an amount added to the weight of the active routine, and subtracted from the weights of all
        # other routines. Calculated from the fade duration and the elapsed time since the last fade
        fade = (now - self._last_fade_time) * (1 / self._fade_duration)
        self._last_fade_time = now
        # increment the weight of the active routine, decrement all others, and produce a new dict of
        # routines containing only those with weights greater than zero. This in effect causes older
        # routines to expire once they're no longer visible
        self._routines = {
            r_id: (r, max(0.0, d - fade) if r_id != self._active_routine else min(1.0, d + fade)) for
            r_id, (r, d) in
            self._routines.items() if d > fade or r_id == self._active_routine}

    def _resolve(self, routine):
        """
        Evaluate a routine. This can accept a constant tuple of either H,S,V or R,G,B,W values
        with all values ranging from 0.0 to 1.0, or a Routine which can be called to generate
        the appropriate values.

        Returns an array of RGBW of length of the number of LEDs in this light
        """
        if isinstance(routine, tuple):
            if len(routine) == 3:
                # treat as constant HSV
                return [self._colour_model.hsv_to_rgbw(*routine)] * self._n
            elif len(routine) == 4:
                # treat as constant RGBW
                return [RGBW(*routine)] * self._n
            else:
                raise ValueError(f'Unable to create a routine from {routine}')
        elif isinstance(routine, Routine):
            return routine.get_rgbw_array(colour_model=self._colour_model)
        elif isinstance(routine, RGBW):
            return [routine] * self._n

    def show(self):
        # Only run if there are routines to show
        if self._routines:
            # Get the total weights, this is always at least 1.0 so we can fade from
            # black without problems when there's only a single routine
            total_weight = self.weights
            # For each routine, multiply every evaluated rgbw value by the proportion of
            # the total weight contributed by this routine
            weighted_routines = [[rgbw * (d / total_weight) for rgbw in self._resolve(routine)] for _, (routine, d) in
                                 self._routines.items()]
            # Zip all resolved routines together and add the rgbw values at each position
            # to get an array of rgbw
            colours = [sum(x) for x in zip(*weighted_routines)] if weighted_routines else [RGBW(0, 0, 0, 0)] * self._n
            if neopixel:
                # Copy colour values to the actual hardware and update the strip
                for i, rgbw in enumerate(colours):
                    self._pixels[i] = rgbw.rgbw8
                self._pixels.show()
            # Fade any routines, bringing the active one into view and fading others away
            self._fade_routines()

    @property
    def brightness(self):
        if neopixel:
            return self._pixels.brightness
        return 1.0

    @brightness.setter
    def brightness(self, value):
        if neopixel:
            self._pixels.brightness = value

    @property
    def fade(self):
        return self._fade_duration

    @fade.setter
    def fade(self, value):
        self._fade_duration = max(0.01, value)

    @property
    def routine(self):
        if self._active_routine is None:
            return None
        return self._routines[self._active_routine][0]

    @routine.setter
    def routine(self, r):
        """
        Set a new routine. It comes into being at 0 brightness, this will then be faded in
        over time to avoid abrupt transitions.

        :param r:
            A routine, this can be anything the _resolve function can use.
        """
        self._active_routine = str(uuid.uuid4())
        self._routines[self._active_routine] = r, 0

    @property
    def weights(self):
        """
        Total of all the routine weights, with a minimum of 1.0
        """
        return max(1.0, sum([d for _, (_, d) in self._routines.items()]))

    @property
    def n(self) -> int:
        """
        Number of LEDs in the strip
        """
        return self._n

    @property
    def pixels(self):
        """
        If present, the underlying neopixel object, otherwise None
        """
        return self._pixels if neopixel else None

    @property
    def colour_model(self) -> RGBWColour:
        """
        The RGBWColour used by this object to manage transformation into RGBW space
        """
        return self._colour_model


# Defines a set of routines which are cycled using the dimmer switch. Routines can be
# instances of Routine, constant RGBW instances, or hsv or rgbw tuples.
routines = [
    Rainbows(),
    Sparkle(),
    RGBW(0.1, 0, 0, 1.0),
    RGBW(0, 0, 0, 0)
]


class DimmerSwitch:
    """
    Handles subscription to MQTT to listen for button events from a Hue dimmer switch
    """

    def __init__(self, switch_name, client_name, lights, broker='unifi.local', user='mqtt', password='mqtt'):
        self._lights = lights
        self._client = mqtt.Client(client_name)
        self._client.username_pw_set(username=user, password=password)
        self._client.connect(host=broker)
        self._client.loop_start()
        self._client.subscribe(topic=f'hue/{switch_name}/buttonevent', qos=0)
        self._client.on_message = lambda client, user_data, message: self.handle_message(message.payload.decode())
        self._current_routine_index = 0

    def handle_message(self, message):
        button = int(message[0])
        code = int(message[3])
        # x000 - hard press
        # x002 - soft press
        # x001 - button hold
        # x003 - button hold release
        if code == 2 or code == 1:
            # Presses. Currently monitors the on and off buttons, using them
            # to cycle through routines
            if button == 1 or button == 4:
                self.increment_routine(1 if button == 1 else -1)

    def increment_routine(self, delta):
        self._current_routine_index += delta
        self._lights.routine = routines[self._current_routine_index % len(routines)]

    def stop(self):
        self._client.loop_stop()


# Create a lights manager along with an attached colour space
lights = Lights(colour_model=RGBWColour(), n=NUM_PIXELS)
# Create and start an MQTT listener, linking it to the controlled lights
dimmer = DimmerSwitch(switch_name='kitchen_led_control', client_name='kitchen_client', lights=lights)
# Loop, with a small delay to ease off CPU usage on the pi
while True:
    lights.show()
    sleep(0.005)
