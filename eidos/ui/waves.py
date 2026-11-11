"""Reusable wave paths and soft, tapered ribbons; no per-frame blur effects."""
import math
import random
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QLinearGradient, QPainterPath, QPen


class Highlight:
    def __init__(self, layer, slot):
        self.layer = layer
        self.rng = random.Random()
        self.duration = 19 + layer * 3.1 + slot * 5.3
        self.delay = ((.26 + layer * .17 + slot * .43) % 1) * self.duration
        self.cycle = 0
        self.start = self.rng.uniform(.12, .88)
        self.end = self.rng.uniform(.12, .88)
        self.length = self.rng.uniform(.20, .34)
        self.strength = self.rng.uniform(.75, 1.15)
        self.center = self.start
        self.opacity = 0.
        # x, y, normal x, normal y, longitudinal taper. Mutated in place.
        self.points = [[0.] * 5 for _ in range(25)]

    def update(self, seconds):
        position = (seconds + self.delay) / self.duration
        cycle = math.floor(position)
        if cycle != self.cycle:
            self.cycle = cycle
            self.start = self.end
            self.end = self.rng.uniform(.12, .88)
            self.length = self.rng.uniform(.20, .34)
            self.strength = self.rng.uniform(.75, 1.15)
        progress = position - cycle
        ease = progress * progress * (3 - 2 * progress)
        self.center = self.start + (self.end - self.start) * ease
        # Both sides of a cycle boundary are exactly dark: random updates
        # cannot create a visible jump. The center travels continuously inside it.
        self.opacity = self.strength * math.sin(math.pi * progress) ** 2


class WaveRenderer:
    def __init__(self):
        self.paths = [QPainterPath() for _ in range(3)]
        self.ribbon = QPainterPath()
        self.pens = [QPen(QColor(37, 230, 161, 40 - i * 10), 1.2) for i in range(3)]
        self.fill = QLinearGradient()
        self.fill.setColorAt(0, QColor(37, 230, 161, 12))
        self.fill.setColorAt(1, QColor(37, 230, 161, 0))
        self.highlights = [Highlight(layer, slot) for layer in range(3) for slot in range(2)]
        # Nested ribbons approximate a soft transverse falloff. Each tapers
        # along its length, so neither the core nor the halo has abrupt ends.
        self.widths = (136., 112., 88., 68., 50., 36., 24., 14., 7., 3., 1.4)
        self.colors = [QColor(37, 230, 161, a) for a in (1, 1, 2, 2, 3, 4, 5, 7, 13, 28)]
        self.colors.append(QColor(99, 243, 203, 164))

    @staticmethod
    def ordinate(u, height, phase, layer):
        return height - 80 - layer * 17 + math.sin(u * 2 * math.pi + phase * 2 * math.pi / 16 + layer * .7) * (23 + layer * 10 + 3 * math.sin(phase * 4 * math.pi / 16))

    def draw(self, painter, width, height, phase):
        if width <= 0:
            return
        self.fill.setStart(0, height - 170)
        self.fill.setFinalStop(0, height)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for layer, path in enumerate(self.paths):
            path.clear()
            path.moveTo(0, self.ordinate(0, height, phase, layer))
            for i in range(1, 81):
                path.lineTo(width * i / 80, self.ordinate(i / 80, height, phase, layer))
            painter.setPen(self.pens[layer])
            painter.drawPath(path)
            path.lineTo(width, height)
            path.lineTo(0, height)
            path.closeSubpath()
            painter.fillPath(path, self.fill)
        painter.setPen(Qt.PenStyle.NoPen)
        for light in self.highlights:
            light.update(phase)
            if light.opacity < .002:
                continue
            amplitude = 23 + light.layer * 10 + 3 * math.sin(phase * 4 * math.pi / 16)
            for index, point in enumerate(light.points):
                progress = index / 24
                u = light.center + (progress - .5) * light.length
                slope = 2 * math.pi * math.cos(u * 2 * math.pi + phase * 2 * math.pi / 16 + light.layer * .7) * amplitude / width
                scale = 1 / math.sqrt(1 + slope * slope)
                point[0] = u * width
                point[1] = self.ordinate(u, height, phase, light.layer)
                point[2] = -slope * scale
                point[3] = scale
                point[4] = math.sin(math.pi * progress) ** 2
            painter.setOpacity(min(1., light.opacity))
            for thickness, color in zip(self.widths, self.colors):
                self.ribbon.clear()
                for index, point in enumerate(light.points):
                    distance = thickness * .5 * point[4]
                    x, y = point[0] + point[2] * distance, point[1] + point[3] * distance
                    if index == 0:
                        self.ribbon.moveTo(x, y)
                    else:
                        self.ribbon.lineTo(x, y)
                for point in reversed(light.points):
                    distance = thickness * .5 * point[4]
                    self.ribbon.lineTo(point[0] - point[2] * distance, point[1] - point[3] * distance)
                self.ribbon.closeSubpath()
                painter.fillPath(self.ribbon, color)
        painter.setOpacity(1.)
