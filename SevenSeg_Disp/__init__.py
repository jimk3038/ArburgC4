#!/usr/bin/env python
# -*- coding: utf-8 -*-
# vim: ai ts=4 sts=4 et sw=4 nu

'''
Segment
=======

The :class:`Segment` widget is a widget for displaying segment.

The value property of segment must be a string.
The scale property of segment must be a float.
The color property of segment must be a list.

Ex::

seg = Segment(scale=0.3, value="A.")

Are permitted : 0 1 2 3 4 5 6 7 8 9 and 0. 1. 2. 3. 4. 5. 6. 7. 8. 9.

and

A b C d E F and A. b. C. d. E. F.

'''

__all__ = ('Segment',)

__title__ = 'garden.segment'
__version__ = '0.21'
__author__ = 'julien@hautefeuille.eu'

import kivy
kivy.require('1.7.1')
from kivy.config import Config
from kivy.app import App
from kivy.properties import StringProperty
from kivy.properties import ListProperty
from kivy.properties import BoundedNumericProperty
from kivy.properties import NumericProperty
from kivy.uix.relativelayout import RelativeLayout
from kivy.graphics import Color, Ellipse, Mesh, Scale, Rectangle
from kivy.utils import get_color_from_hex
from kivy.uix.label import Label


class Segment(RelativeLayout):
    '''
    Segment class

    The class`Segment` widget is a widget for displaying segment.

    The value property of segment must be a string.
    The scale property of segment must be a float.
    The color property of segment must be a string.

    Ex::

    seg = Segment(scale=0.3, value="A.")

    Are permitted : 0 1 2 3 4 5 6 7 8 9 and 0. 1. 2. 3. 4. 5. 6. 7. 8. 9.

    and

    A b C d E F and A. b. C. d. E. F.

    '''

    # Object properties configuration
    scale = BoundedNumericProperty(0.1, min=0.1, max=1, errorvalue=0.2)
    shadow = BoundedNumericProperty(0.4, min=0.0, max=0.91, errorvalue=0.4)
    color = ListProperty( list((1., 0, 0)) )
    value = StringProperty('0')
    width = NumericProperty()

    def __init__(self, **kwargs):     
        super(Segment, self).__init__(**kwargs)

        # Drawing meshes configuration, indices range meshes and mode
        self.indice = xrange(0, 6)
        self.xmode = 'triangle_fan'
        self.shadowColor = [ 
            self.color[0]*self.shadow, 
            self.color[1]*self.shadow, 
            self.color[2]*self.shadow 
        ]
        
        # Segment matrix configuration
        seg_1 = [
                20, 215, 0, 0,
                35, 230, 0, 0,
                95, 230, 0, 0,
                110, 215, 0, 0,
                95, 200, 0, 0,
                35, 200, 0, 0,
                ]
        seg_2 = [
                15, 210, 0, 0,
                30, 195, 0, 0,
                30, 135, 0, 0,
                15, 120, 0, 0,
                0, 135, 0, 0,
                0, 195, 0, 0,
                ]
        seg_3 = [
                115, 210, 0, 0,
                130, 195, 0, 0,
                130, 135, 0, 0,
                115, 120, 0, 0,
                100, 135, 0, 0,
                100, 195, 0, 0,
                ]
        seg_4 = [
                20, 115, 0, 0,
                35, 130, 0, 0,
                95, 130, 0, 0,
                110, 115, 0, 0,
                95, 100, 0, 0,
                35, 100, 0, 0,
                ]
        seg_5 = [
                15, 110, 0, 0,
                30, 95, 0, 0,
                30, 35, 0, 0,
                15, 20, 0, 0,
                0, 35, 0, 0,
                0, 95, 0, 0,
                ]
        seg_6 = [
                115, 110, 0, 0,
                130, 95, 0, 0,
                130, 35, 0, 0,
                115, 20, 0, 0,
                100, 35, 0, 0,
                100, 95, 0, 0,
                ]
        seg_7 = [
                20, 15, 0, 0,
                35, 30, 0, 0,
                95, 30, 0, 0,
                110, 15, 0, 0,
                95, 0, 0, 0,
                35, 0, 0, 0,
                ]

        # Drawing association
        type_0 = [seg_1, seg_2, seg_3, seg_5, seg_6, seg_7]
        type_1 = [seg_3, seg_6]
        type_2 = [seg_1, seg_3, seg_4, seg_5, seg_7]
        type_3 = [seg_1, seg_3, seg_4, seg_6, seg_7]
        type_4 = [seg_2, seg_3, seg_4, seg_6]
        type_5 = [seg_1, seg_2, seg_4, seg_6, seg_7]
        type_6 = [seg_1, seg_2, seg_4, seg_5, seg_6, seg_7]
        type_7 = [seg_1, seg_3, seg_6]
        type_8 = [seg_1, seg_2, seg_3, seg_4, seg_5, seg_6, seg_7]
        type_9 = [seg_1, seg_2, seg_3, seg_4, seg_6, seg_7]
        type_A = [seg_1, seg_2, seg_3, seg_4, seg_5, seg_6]
        type_b = [seg_2, seg_4, seg_5, seg_6, seg_7]
        type_C = [seg_1, seg_2, seg_5, seg_7]
        type_d = [seg_3, seg_4, seg_5, seg_6, seg_7]
        type_E = [seg_1, seg_2, seg_4, seg_5, seg_7]
        type_F = [seg_1, seg_2, seg_4, seg_5]

        # Drawing association for shadows.
        type_0s = [ seg_4 ]
        type_1s = [ seg_1, seg_2, seg_4, seg_5, seg_7 ]
        type_2s = [ seg_2, seg_6 ]
        type_3s = [ seg_2, seg_5 ]
        type_4s = [ seg_1, seg_5, seg_7 ]
        type_5s = [ seg_3, seg_5 ]
        type_6s = [ seg_3 ]
        type_7s = [ seg_2, seg_4, seg_5, seg_7 ]
        type_8s = [ ]
        type_9s = [ seg_5 ]
        type_As = [ seg_7 ]
        type_bs = [ seg_1, seg_3 ]
        type_Cs = [ seg_3, seg_4, seg_6 ]
        type_ds = [ seg_1, seg_2, ]
        type_Es = [ seg_3, seg_6 ]
        type_Fs = [ seg_3, seg_6, seg_7 ]

        # Routing association
        self.type_dic = {
                "0" : type_0,
                "0.": type_0,
                "1" : type_1,
                "1.": type_1,
                "2" : type_2,
                "2.": type_2,
                "3" : type_3,
                "3.": type_3,
                "4" : type_4,
                "4.": type_4,
                "5" : type_5,
                "5.": type_5,
                "6" : type_6,
                "6.": type_6,
                "7" : type_7,
                "7.": type_7,
                "8" : type_8,
                "8.": type_8,
                "9" : type_9,
                "9.": type_9,
                "A" : type_A,
                "A.": type_A,
                "b" : type_b,
                "b.": type_b,
                "C" : type_C,
                "C.": type_C,
                "d" : type_d,
                "d.": type_d,
                "E" : type_E,
                "E.": type_E,
                "F" : type_F,
                "F.": type_F,
                }

        # Routing association for shadows.
        self.type_dic_s = {
                "0" : type_0s,
                "0.": type_0s,
                "1" : type_1s,
                "1.": type_1s,
                "2" : type_2s,
                "2.": type_2s,
                "3" : type_3s,
                "3.": type_3s,
                "4" : type_4s,
                "4.": type_4s,
                "5" : type_5s,
                "5.": type_5s,
                "6" : type_6s,
                "6.": type_6s,
                "7" : type_7s,
                "7.": type_7s,
                "8" : type_8s,
                "8.": type_8s,
                "9" : type_9s,
                "9.": type_9s,
                "A" : type_As,
                "A.": type_As,
                "b" : type_bs,
                "b.": type_bs,
                "C" : type_Cs,
                "C.": type_Cs,
                "d" : type_ds,
                "d.": type_ds,
                "E" : type_Es,
                "E.": type_Es,
                "F" : type_Fs,
                "F.": type_Fs,
                }

        # Binding refresh drawing method
        self.bind(
            pos=self._update_canvas, 
            size=self._update_canvas,
            value=self._update_canvas
            )

    def _update_canvas(self, *args):

        with self.canvas:

            # Refresh
            self.canvas.clear()

            # Scale
            Scale(self.scale)

            self.shadowColor = [ 
                self.color[0]*self.shadow, 
                self.color[1]*self.shadow, 
                self.color[2]*self.shadow 
            ]

            # Draw meshes
            def make_mesh(self, ttype, *args):
                ''' Drawing meshes
                '''
                for segment in ttype:
                    Mesh(
                        vertices=segment, 
                        indices=self.indice, 
                        mode=self.xmode
                        )
                if len(self.value) > 1:
                    Color( self.color[0], self.color[1], self.color[2] )
                Ellipse(
                    pos=(135, 0), 
                    size=(25,25), 
                    segments=360
                    )


            # Avoid if session
            Color( self.color[0], self.color[1], self.color[2] )
            for key, val in self.type_dic.items():
                if self.value == key:
                    make_mesh(self, ttype=val)

            # Draw other segments in shadow.
            Color( self.shadowColor[0], self.shadowColor[1], self.shadowColor[2] ) 
            for key, val in self.type_dic_s.items():
                if self.value == key:
                    make_mesh(self, ttype=val)

      


class SegmentTestApp(App):
    
    def build(self):
        from kivy.clock import Clock
        from kivy.uix.stacklayout import StackLayout

        def refresh_task(self, *args):
            global counts
            s = "{:04.1f}".format( counts )
            seg.value = s[0]
            seg1.value = s[1:3]
            seg2.value = s[3]
            counts += 0.1

        box = StackLayout( orientation='lr-tb' )
        box.padding = 10

        w = 75
        h = 100
        seg = Segment(scale=0.4, value="0", width=w, height=h, size_hint=(None,None) )
        seg1 = Segment(scale=0.4, value="0.", width=w, height=h, size_hint=(None,None) )
        seg2 = Segment(scale=0.25, value="0", width=w, height=h, size_hint=(None,None) )
        
        box.add_widget(seg)
        box.add_widget(seg1)
        box.add_widget(seg2)

        Clock.schedule_interval( refresh_task, 0.1 )

        return box
            
if __name__ == '__main__':
    counts = 0.0
    SegmentTestApp().run()

