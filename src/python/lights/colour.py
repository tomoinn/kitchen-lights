import colorsys


class RGBWColour:
    """
    Colour transformation and management, attempts to convert from hsv to rgbw with
    various options for gamma and saturation correction
    """

    def __init__(self):
        self._gamma = 2.0
        self._saturation = 2.0
        self._brightness = 1.0

    @property
    def brightness(self):
        return self._brightness

    @brightness.setter
    def brightness(self, value):
        self._brightness = max(0, 0, min(value, 1.0))

    @property
    def saturation(self):
        return self._saturation

    @saturation.setter
    def saturation(self, value):
        self._saturation = max(0.0, value)

    @property
    def gamma(self):
        return self._gamma

    @gamma.setter
    def gamma(self, value):
        self._gamma = max(0.0, value)

    def hsv_to_rgbw(self, hue, sat, value, white=None):
        """
        Convert from hsv to rgbw colour space. Attempts to do this by setting the RGB component of the strip
        to the colour after setting saturation to 1.0, then blending in an amount of the white chip. When
        the target saturation is less than 1, this is also used to scale the brightness of the colour component
        back, so very low saturation produces very dim colours along with a predominant white component. This
        isn't particularly scientific, but produces plausible results. RGB values are modified by the gamma
        value set on this colour space.

        :param hue:
            Hue, 0.0 to 1.0 (but other values will wrap)
        :param sat:
            Saturation, 0.0 to 1.0
        :param value:
            Value, 0.0 to 1.0
        :param white:
            If specified, explicitly set the white LED to this value. Defaults to None, in which
            case the white LED value is set from the hsv->rgbw algorithm
        :return:
        """
        sat = sat ** (1 / self._saturation) if self._saturation > 0 else 0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, value * self._brightness * sat)
        w = (1 - sat) * value * self._brightness if white is None else white * self._brightness
        return RGBW(r ** self._gamma, g ** self._gamma, b ** self._gamma, w)


class RGBW:
    """
    Represents a single RGBW tuple, with convenience methods to scale or add two tuples together. All values
    are 0.0 to 1.0
    """

    def __init__(self, r, g, b, w):
        self.r = r
        self.g = g
        self.b = b
        self.w = w

    def __add__(self, other):
        if isinstance(other, RGBW):
            return RGBW(r=self.r + other.r,
                        g=self.g + other.g,
                        b=self.b + other.b,
                        w=self.w + other.w)
        return self

    def __radd__(self, other):
        return self.__add__(other)

    def __mul__(self, other):
        return RGBW(r=self.r * other,
                    g=self.g * other,
                    b=self.b * other,
                    w=self.w * other)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __str__(self):
        return f'rgbw({self.r},{self.g},{self.b},{self.w})'

    def __repr__(self):
        return self.__str__()

    @property
    def rgbw8(self):
        """
        Get a 0-255 version of the r, g, b, w values, as used by a neopixel or similar
        """
        return self.r * 255, self.g * 255, self.b * 255, self.w * 255
