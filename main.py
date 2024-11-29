import time
import math
import sys
from typing import Callable, Union
import dataclasses
from dataclasses import dataclass
from itertools import combinations, combinations_with_replacement

# gui
import tkinter as tk
from tkinter import colorchooser
import customtkinter as ctk
from CTkToolTip import CTkToolTip
# eye dropper
import pyscreeze
from pynput.mouse import Listener
# json
import json


###################################
#           Model App
###################################

# Item data
@dataclass
class Color:
    rgb: tuple[int, int, int] = None
    hex_: int = None
    name: str = ''
    id: str = '-1'

    def __post_init__(self):
        if self.hex_ is None and self.rgb is not None:
            self.set_rgb(self.rgb)
        elif self.rgb is None and self.hex_ is not None:
            self.set_hex(self.hex_)
        elif self.rgb is None and self.hex_ is None:
            self.set_hex(0)

    def set_rgb(self, rgb):
        self.hex_ = Color.get_hex_value(rgb)
        self.rgb = rgb

    def set_hex(self, hex_value):
        self.hex_ = hex_value
        self.rgb = Color.get_rgb_value(hex_value)

    def set(self, color):
        self.set_rgb(color.rgb)

    def get_hex(self):
        r, g, b = self.rgb
        return f'#{r:02x}{g:02x}{b:02x}'

    def get_bright(self):
        r, g, b = self.rgb
        return int((r + g + b) / 3)

    @staticmethod
    def get_hex_value(rgb):
        r, g, b = rgb
        return (r << 16) | (g << 8) | b

    @staticmethod
    def get_rgb_value(hex_):
        return (
            hex_ >> 16,
            (hex_ >> 8) & 0xff,
            hex_ & 0xff
        )


class Observer:

    def __init__(self):
        self._listeners = list()

    def add_event(self, listener):
        self._listeners.append(listener)

    def dispatch_event(self, event_name: str = None):
        for listener in self._listeners:
            listener(event_name)


class Model(Observer):
    evt_fav_added = 'add_favorite'
    evt_fav_removed = 'remove_favorite'
    evt_fav_loaded = 'loaded_favorite'

    evt_colors_loaded = 'loaded_colors'

    def __init__(self):
        super().__init__()
        self.colors = list()
        self.favorite = list()

    def set_data(self, colors):
        for item in colors:
            self.colors.append(
                Color(name=item['name'], id=item['id'], hex_=item['value'])
            )

    def add_favorite(self, blends, dispach=True):
        print(f'add favorite {len(blends)}')
        self.favorite.append({
            'colors': blends,
            'new': self.blend_colors(blends)
        })
        if dispach: self.dispatch_event(Model.evt_fav_added)

    def remove_favorite(self, index, dispach=True):
        print('remove favorite')
        fav = self.favorite[index]
        self.favorite.remove(fav)
        if dispach: self.dispatch_event(Model.evt_fav_removed)

    def get_json_favorite(self):
        return Model.encoder_json(self.favorite)

    def get_json_colors(self):
        return Model.encoder_json(self.colors)

    def set_json_favorite(self, str_json):
        self.favorite = Model.decoder_json(str_json)
        self.dispatch_event(Model.evt_fav_loaded)

    def set_json_colors(self, str_json):
        self.colors = Model.decoder_json(str_json)
        self.dispatch_event(Model.evt_colors_loaded)

    # busca el mejor blends(mezcla) para un color determinado
    # devuelve un array de blends con x% de precision
    # se ordena por su distancia rgb
    def find_blend(
            self, color_target,
            precision=0.9, color_max=4, cant_max=4):
        count = 0
        result = list()
        len_colors = len(self.colors)
        for index_color in range(1, color_max + 1):
            # crea una lista de combinaciones de indexs de un array
            # en este caso de la comb. de colores que se pueden mezclar a la vez
            comb_colors = list(combinations(range(len_colors), index_color))
            # combinacion de la cantidad de color de cada color con duplicaciones
            amount_colors = list(combinations_with_replacement(range(1, cant_max + 1), index_color))
            for comb_color in comb_colors:
                for amount_color in amount_colors:
                    colors = list()
                    for index, amount in enumerate(amount_color):
                        color = self.colors[comb_color[index]]
                        colors.append(
                            {'amount': amount, 'color': color}
                        )
                    new_color = self.blend_colors(colors)
                    d = self.distance(new_color, color_target)
                    # buscamos en el resultado si hay blends duplicados
                    found = None
                    for k in result:
                        if d == k['d']:  # new.hex_ == k['new'].hex_
                            found = True
                            break
                    count += 1
                    if d > precision and found is None:
                        result.append(
                            {'colors': colors, 'd': d, 'new': new_color}
                        )

        print(f'iteraciones {count} numero de resultados {len(result)}')
        # se ordena por la distancia rgb
        result.sort(key=lambda x: x['d'], reverse=True)
        return result

    #
    #         Static methods

    # json decoder 
    @staticmethod
    def as_color(dct):
        if 'rgb' in dct:
            return Color(**dct)
        return dct

    # json encoder
    @staticmethod
    def encoder_json(data):
        json_string = json.dumps(
            data, cls=DataclassJSONEncoder, indent=4)
        return json_string

    @staticmethod
    def decoder_json(json_string):
        data = json.loads(
            json_string,
            object_hook=Model.as_color
        )
        return data

    @staticmethod
    # Calculate the Euclidean distance between two RGB colors return 0-1(%)
    def distance(c1, c2):
        r1, g1, b1 = c1.rgb
        r2, g2, b2 = c2.rgb
        r, g, b = r1 - r2, g1 - g2, b1 - b2

        '''max_ = 441.6729559300637 # maximum distance between black and white
        return 1 - (math.sqrt(r ** 2 + g ** 2 + b ** 2) / max_)'''

        max_ = 764.8339663572415  # maximum distance between black and white

        r_mean = (r1 + r2) / 2
        weight_r = 2 + r_mean / 256
        weight_g = 4.0
        weight_b = 2 + (255 - r_mean) / 256
        return 1 - (math.sqrt(weight_r * r * r + weight_g * g * g + weight_b * b * b) / max_)

    # devuelve la mezcla de un array de colores
    # cada color del array tiene su cantidad (gotas)
    @staticmethod
    def blend_colors(colors):
        total = 0
        rt, gt, bt = 0, 0, 0
        for colorD in colors:
            amount = colorD['amount']
            color = colorD['color']
            rt += color.rgb[0] * amount
            gt += color.rgb[1] * amount
            bt += color.rgb[2] * amount
            total += amount
        return Color(rgb=(
            round(rt / total),
            round(gt / total),
            round(bt / total)
        ))


###################################
#            tools
###################################

def get_color_label(color):
    # str = "white" if color.get_bright() < 128 else "black"
    if color.get_bright() < 128:
        return "white"
    else:
        return "black"


class DataclassJSONEncoder(json.JSONEncoder):
    def default(self, o):
        if dataclasses.is_dataclass(o):
            return dataclasses.asdict(o)
        return super().default(o)


###################################
#        generic widgets 
###################################

class CTkListbox(ctk.CTkScrollableFrame):

    def __init__(self, master, command=None, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color='grey94')
        self.index = None
        self.grid_columnconfigure(0, weight=1)
        self.command = command
        self.widgets = list()

    def remove_item(self, index):
        if index < len(self.widgets):
            widget = self.widgets[index]
            widget.destroy()
            self.widgets.remove(widget)
            # update widget row position
            for i in range(index, len(self.widgets)):
                widget = self.widgets[i]
                widget.grid(row=i)

    def remove_items(self):
        for widget in self.widgets:
            widget.destroy()

        self.widgets.clear()

    def onclick(self, events):
        index = -1
        for index, button in enumerate(self.widgets):
            if events.widget.master is button:
                index = index
                break

        if index < 0: return

        self.set(index)

        if self.command is not None:
            self.command(index)

    def get(self):
        return self.index

    def set(self, index):
        if index < len(self.widgets):
            self.index = index

    def add_item(self, container):
        self.widgets.append(container)


class CTKWinBox(ctk.CTkToplevel):

    def __init__(self,
                 master: any = None,
                 width: int = 500,
                 height: int = 300,
                 title: str = "CTkMessagebox",
                 **kwargs):
        super().__init__(master, **kwargs)
        self.attributes("-topmost", True)
        self.configure(corner_radius=0)
        self.width = 200 if width < 200 else width
        self.height = 300 if height < 300 else height

        self.spawn_x = int((self.winfo_screenwidth() - self.width) / 2)
        self.spawn_y = int((self.winfo_screenheight() - self.height) / 2)

        self.after(10)
        # self.geometry(f"{self.width}x{self.height}+{self.spawn_x}+{self.spawn_y}")
        self.title(title)
        self.resizable(width=False, height=False)

        self.overrideredirect(True)

        # self.transparent_color = self._apply_appearance_mode(self.cget("fg_color"))
        # self.attributes("-transparentcolor", self.transparent_color)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        self.x = self.winfo_x()
        self.y = self.winfo_y()
        self._title = title

        self.frame_top = ctk.CTkFrame(
            self, width=self.width,
            fg_color='grey82', corner_radius=0
        )
        self.frame_top.grid_rowconfigure((1, 2, 3), weight=1)
        self.frame_top.columnconfigure((0, 1, 2, 3, 4, 5), weight=1)
        self.frame_top.grid(row=0, column=0, sticky="nswe")

        self.frame_top.bind("<B1-Motion>", self.move_window)
        self.frame_top.bind("<ButtonPress-1>", self.oldxyset)

        self.button_close = ctk.CTkButton(self.frame_top, corner_radius=10, width=0, height=0,
                                          hover=False, border_width=0,
                                          text_color='black',
                                          text="✕", fg_color="transparent", command=self.onclick)
        self.button_close.grid(row=0, column=5, sticky="ne", padx=5, pady=5)

        self.title_label = ctk.CTkLabel(self.frame_top, text=self._title, text_color='black')
        self.title_label.grid(row=0, column=0, columnspan=6, sticky="nw", padx=(15, 30), pady=5)
        self.title_label.bind("<B1-Motion>", self.move_window)
        self.title_label.bind("<ButtonPress-1>", self.oldxyset)

        self.container = ctk.CTkFrame(self.frame_top)
        self.container.grid(row=1, column=0, columnspan=6, sticky="nwes", padx=0)
        self.container.columnconfigure(0, weight=1)

        self.buttons = ctk.CTkFrame(self.frame_top, fg_color='transparent')
        self.buttons.grid(row=2, column=0, columnspan=6, )
        # self.buttons.columnconfigure((0,1,2,3), weight=1)

        self.button_close = ctk.CTkButton(self.buttons, text='Cerrar', width=50, command=self.onclick)
        self.button_close.grid(row=0, column=0, padx=5, pady=5)

        # self.button_close = ctk.CTkButton(self.buttons, text='Cerrar', command=self.onclick)
        # self.button_close.grid(row=0, column=1, padx=5, pady=5)

        self.bind("<Escape>", lambda e: self.onclick())

        self.lift()

    def get(self):
        if self.winfo_exists():
            self.master.wait_window(self)
        return self.event

    def oldxyset(self, event):
        self.oldx = event.x
        self.oldy = event.y

    def move_window(self, event):
        self.y = event.y_root - self.oldy
        self.x = event.x_root - self.oldx
        self.geometry(f'+{self.x}+{self.y}')

    def onclick(self, event=None):
        self.destroy()
        self.event = event


class CTkSpinbox(ctk.CTkFrame):
    def __init__(self, *args,
                 width: int = 100,
                 height: int = 32,
                 from_: int = 1, to: int = 99,
                 step_size: int = 1,
                 command: Callable = None,
                 **kwargs):
        super().__init__(*args, width=width, height=height, **kwargs)

        self._from = from_
        self._to = to

        self.step_size = step_size
        self.command = command

        self.configure(fg_color=("gray78", "gray28"))  # set frame color

        self.grid_columnconfigure((0, 2), weight=0)  # buttons don't expand
        self.grid_columnconfigure(1, weight=1)  # entry expands

        self.subtract_button = ctk.CTkButton(self, text="-", width=height - 6, height=height - 6,
                                             command=self.subtract_button_callback)
        self.subtract_button.grid(row=0, column=0, padx=(3, 0), pady=3)

        self.entry = ctk.CTkEntry(self, width=width - (2 * height), height=height - 6, border_width=0)
        self.entry.grid(row=0, column=1, columnspan=1, padx=3, pady=3, sticky="ew")

        self.add_button = ctk.CTkButton(self, text="+", width=height - 6, height=height - 6,
                                        command=self.add_button_callback)
        self.add_button.grid(row=0, column=2, padx=(0, 3), pady=3)

        # default value
        self.entry.insert(0, "0")

    def add_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = int(self.entry.get()) + self.step_size
            self.set(value)
        except ValueError:
            return

    def subtract_button_callback(self):
        if self.command is not None:
            self.command()
        try:
            value = int(self.entry.get()) - self.step_size
            self.set(value)
        except ValueError:
            return

    def get(self) -> Union[int, None]:
        try:
            return int(self.entry.get())
        except ValueError:
            return None

    def set(self, value: int):
        if value >= self._from and value <= self._to:
            self.entry.delete(0, "end")
            self.entry.insert(0, str(value))


class CTKEyeDropper(ctk.CTkToplevel):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.configure(corner_radius=0, cursor="none")
        self.attributes("-topmost", True)

        self.color = None
        self.dia = 60
        self.center = int(self.dia / 2)

        self.geometry(f"{self.dia}x{self.dia}")
        self.resizable(width=False, height=False)

        self.overrideredirect(True)

        self.transparent_color = 'grey99'
        self.attributes("-transparentcolor", self.transparent_color)

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        self.canvas = tk.Canvas(
            self,
            highlightthickness=0,
            bg=self.transparent_color,
            width=self.dia,
            height=self.dia
        )
        self.canvas.grid(row=0, column=0, sticky="nswe")

        # draw
        color = "white"
        self.out_shape = self.canvas.create_oval(
            0, 0,
            self.dia - 1, self.dia - 1,
            fill=color
        )
        w = 20
        self.canvas.create_oval(
            w, w,
            self.dia - w, self.dia - w,
            fill=self.transparent_color
        )

        self.after(100)

        self.listener = Listener(on_move=self.on_move,
                                 on_click=self.on_click)
        self.listener.start()

    def get(self):
        if self.winfo_exists():
            self.master.wait_window(self)
        return self.color

    def on_move(self, x, y):
        self.x = x - self.center
        self.y = y - self.center
        try:
            self.color = pyscreeze.pixel(x, y)
            r, g, b = self.color
            str_color = f'#{r:02x}{g:02x}{b:02x}'
            self.canvas.itemconfigure(self.out_shape, fill=str_color)
            self.geometry(f'+{self.x}+{self.y}')
        except:
            error = 1

        # print(f"RGB: {self.color[0]}, {self.color[1]}, {self.color[2]}")

    def on_click(self, x, y, button, pressed):
        if pressed:
            self.destroy()
            return False  # Stop listener


###################################
#         Widgets App
###################################

class GalleryColor(CTkListbox):

    def __init__(self, master, command=None, columns=2, **kwargs):
        super().__init__(master, command, **kwargs)

        self.col = columns

    def add_item(self, color=None):
        txt, fg_color, color_text = '', '#ffffff', 'black'

        if color is not None:
            color_text = get_color_label(color)
            fg_color = color.get_hex()
            txt = color.name

        button = ctk.CTkButton(self, text=txt, fg_color=fg_color,
                               border_width=0, border_color=('#3B8ED0', '#1F6AA5'),
                               text_color=color_text,
                               width=120, height=100, hover=False)
        button.bind("<Button-1>", self.onclick)

        tooltip = CTkToolTip(button, message=f'{color.rgb}\n{fg_color}')

        i = len(self.widgets)
        row = i // self.col
        col = i % self.col

        button.grid(row=row, column=col, pady=(0, 10), padx=5)

        super().add_item(button)

    def set(self, index):
        if index < len(self.widgets):
            if self.index is not None:
                self.widgets[self.index].configure(border_width=0)
            self.index = index
            item = self.widgets[index]
            item.configure(border_width=4)


class ListBlend(CTkListbox):

    def __init__(self, master, command=None, command_removed=None, edit=True, **kwargs):
        super().__init__(master, command, **kwargs)
        self.edit = edit
        self.command_removed = command_removed

    def add_item(self, blend=None, color=None):
        if blend is not None:
            color = blend['color']
            cant = blend['amount']
            txt = f'{color.name} + {cant}'
        elif color is not None:
            txt = f'{color.get_hex()}'

        color_text = get_color_label(color)
        str_color = color.get_hex()

        row = len(self.widgets)

        container = ctk.CTkFrame(master=self, fg_color=str_color)
        container.bind("<Button-1>", self.onclick)
        container.grid_columnconfigure(0, weight=1)
        container.grid(row=row, column=0, pady=(0, 10), padx=5, sticky="nsew")

        label = ctk.CTkLabel(container, text=txt, text_color=color_text)
        label.grid(row=0, column=0)

        CTkToolTip(container, message=f'{color.rgb}\n{str_color}')

        if self.edit:
            button = ctk.CTkButton(container, text='Borrar', width=100)
            button.bind("<Button-1>", self.onclick)
            button.grid(row=0, column=1, pady=10, padx=10)

        super().add_item(container)

    def onclick(self, events):
        if self.edit:
            for index, item in enumerate(self.widgets):
                if events.widget.master.master is item:
                    self.remove_item(index)
                    if self.command_removed is not None:
                        self.command_removed(index)
                    break
                elif events.widget.master is item:
                    if self.command is not None:
                        self.command(index)

        else:
            super().onclick(events)


class WinResult(CTKWinBox):
    def __init__(self,
                 width: int = 200,
                 height: int = 400,
                 title: str = "Resultado",
                 model=None,
                 target=True,
                 **kwargs):
        super().__init__(width=width, height=height, title=title, **kwargs)

        self.model = model
        self.blends = None
        self.target = None

        label = ctk.CTkLabel(self.container, text="Blend Color", font=ctk.CTkFont(size=20, weight="bold"))
        label.grid(row=0, column=0, padx=20, pady=10)

        self.list_blend = ListBlend(master=self.container, edit=False)
        self.list_blend.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        self.result = ctk.CTkLabel(master=self.container, text='',
                                   height=50, fg_color='white')
        self.result.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.result_ttip = CTkToolTip(self.result)
        if target:
            self.target = ctk.CTkLabel(master=self.container, text='',
                                       height=50, fg_color='white')
            self.target.grid(row=2, column=0, padx=0, pady=0, sticky="nsew")
            self.target_ttip = CTkToolTip(self.target)

            save = ctk.CTkButton(self.buttons, text='Guardar fav.', command=self.onsave)
            save.grid(row=0, column=1, padx=5, pady=5)

    def set_data(self, blends, target_color=None):
        self.blends = blends
        self.list_blend.remove_items()

        print(blends)

        for blend in blends['colors']:
            self.list_blend.add_item(blend)

        color = blends['new']

        self.result.configure(text=color.get_hex(),
                              text_color=get_color_label(color),
                              fg_color=color.get_hex())
        self.result_ttip.configure(message=f'{color.rgb}\n{color.get_hex()}')

        if self.target is not None and target_color is not None:
            self.target.configure(text=target_color.get_hex(),
                                  text_color=get_color_label(target_color),
                                  fg_color=target_color.get_hex())
            self.target_ttip.configure(message=f'{target_color.rgb}\n{target_color.get_hex()}')

    def onsave(self, event=None):
        self.event = event
        self.model.add_favorite(self.blends['colors'])


###################################
#               Views
###################################
class View(ctk.CTkFrame):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, **kwargs)
        self.model: Model = model


# busca la mejor combinacion de un color
class ViewFind(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        self.model.add_event(self.update_result)

        self.eye_dropper = None
        self.tooltips = list()
        self.blends = None
        self.result_win = None

        self.target_color = Color(rgb=(255, 192, 203))  # pink

        # configure grid layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar_frame = ctk.CTkFrame(master=self, width=140, corner_radius=0)
        sidebar_frame.grid_rowconfigure(3, weight=1)
        sidebar_frame.grid(row=0, column=0, rowspan=4, sticky="nsew")

        print(self.cget('fg_color'))
        print(sidebar_frame.cget('fg_color'))

        form_frame = ctk.CTkFrame(master=sidebar_frame)
        form_frame.grid(row=0, column=0, padx=20, pady=(20, 10))

        labels = ['Precision', 'Color. max.', 'Cant. max.']
        for row, label_text in enumerate(labels):
            label = ctk.CTkLabel(form_frame, text=label_text)
            label.grid(row=row, column=0, padx=20, pady=(20, 20))

        txtvars = (90, 4, 4)
        maxvalue = (99, 10, 10)
        namevars = ('precision', 'color_max', 'cant_max')
        self.inputs = {}
        for row, var in enumerate(txtvars):
            input = CTkSpinbox(master=form_frame, from_=1, to=maxvalue[row])
            input.set(var)
            input.grid(row=row, column=1, padx=10, pady=5)
            self.inputs[namevars[row]] = input

        self.btn_color = ctk.CTkButton(
            master=sidebar_frame, text='Seleccionar color',
            fg_color=self.target_color.get_hex(),
            text_color=get_color_label(self.target_color),
            command=self.select_color
        )
        self.btn_color.grid(row=1, column=0, padx=20, pady=(0, 10))
        self.btn_eye = ctk.CTkButton(
            master=sidebar_frame, text='Cuenta Gotas',
            fg_color=self.target_color.get_hex(),
            text_color=get_color_label(self.target_color),
            command=self.open_eye_dropper
        )
        self.btn_eye.grid(row=2, column=0, padx=20, pady=(0, 10))

        button = ctk.CTkButton(master=sidebar_frame, text='Buscar',
                               command=self.find_color)
        button.grid(row=4, column=0, padx=20, pady=(0, 10))

        # right frame
        right_frame = ctk.CTkFrame(master=self, corner_radius=0, fg_color='grey92')
        right_frame.grid_columnconfigure(1, weight=0)
        right_frame.grid_columnconfigure((0, 3), weight=1)
        right_frame.grid_rowconfigure(1, weight=0)
        right_frame.grid_rowconfigure((0, 3), weight=1)
        right_frame.grid(row=0, column=1, sticky="nsew")

        center_frame = ctk.CTkFrame(master=right_frame)
        center_frame.grid(row=1, column=1, sticky="nsew")

        self.grid_cells = list()
        index = 0
        # Cuadrícula de 3x3
        for i in range(3):
            for j in range(3):
                index += 1
                cell = ctk.CTkLabel(center_frame, text=f'{index} ', fg_color='white',
                                    width=100, height=100)
                cell.bind("<Button-1>", self.show_blend)
                cell.grid(row=i, column=j)
                self.grid_cells.append(cell)
                tooltip = CTkToolTip(cell)
                tooltip.hide()
                self.tooltips.append(tooltip)

    def show_blend(self, events):
        index = None
        for row, label1 in enumerate(self.grid_cells):
            if events.widget.master is label1:
                index = row
                break

        print('press', index)

        if index is None or self.blends is None or index >= len(self.blends):
            return

        blends = self.blends[index]

        if sys.platform.startswith("win"):
            if self.result_win is None or not self.result_win.winfo_exists():
                self.result_win = WinResult(model=self.model)
        else:
            if self.result_win is not None or not self.result_win.winfo_exists():
                self.result_win.destroy()  # create window if its None or destroyed
            self.result_win = WinResult(model=self.model)

        self.result_win.set_data(blends, self.target_color)
        self.result_win.focus()

    def set_target_color(self, rgb):
        self.target_color.set_rgb(rgb)
        str_color = self.target_color.get_hex()
        txt_color = get_color_label(self.target_color)
        self.btn_color.configure(
            fg_color=str_color,
            text_color=txt_color
        )
        self.btn_eye.configure(
            fg_color=str_color,
            text_color=txt_color
        )

    def select_color(self):
        color = colorchooser.askcolor(
            initialcolor=self.target_color.get_hex(),
            title="Seleccionar color"
        )
        if color[0] is not None:
            self.set_target_color(color[0])

    def open_eye_dropper(self):
        if self.eye_dropper is None or not self.eye_dropper.winfo_exists():
            self.eye_dropper = CTKEyeDropper()  # create window if its None or destroyed
        else:
            self.eye_dropper.focus()  # if window exists focus it

        color = self.eye_dropper.get()
        if color is not None:
            self.set_target_color(color)
            # print(f"RGB: {color[0]}, {color[1]}, {color[2]}")

    def find_color(self):

        prec = self.inputs['precision'].get()
        co_max = self.inputs['color_max'].get()
        cant = self.inputs['cant_max'].get()

        start = time.time()
        self.blends = self.model.find_blend(self.target_color, prec / 100, co_max, cant)[:9]
        print('elapsed :', time.time() - start)

        for blend in self.blends:
            strprint = ''
            for item in blend['colors']:
                strprint += f"{item['color'].name} - {item['color'].rgb} * {item['amount']} + "

            print(strprint[:-1] + f"   d: {blend['d']} new:{blend['new'].rgb} ")

        self.blends.insert(4, {
            'colors': [
                {'color': self.target_color, 'amount': 1}
            ], 'd': 1, 'new': self.target_color
        })

        print(f"Target rgb value {self.target_color.rgb} '{self.target_color.get_hex()}' ")

        self.update_result()

    def update_result(self, event_name=None):
        for index, cell in enumerate(self.grid_cells):
            tooltip = self.tooltips[index]
            if self.blends is not None and index + 1 <= len(self.blends):
                color = self.blends[index]['new']
                color_str = color.get_hex()
                cell.configure(fg_color=color_str, text=color_str,
                               text_color=get_color_label(self.blends[index]['new']))
                tooltip.configure(message=f'{color.rgb}\n{color_str}')
                tooltip.show()
            else:
                cell.configure(fg_color='white', text='')
                tooltip.hide()

    def clear_results(self, event_name):
        if event_name == Model.evt_colors_loaded:
            self.blends.clear()
            self.update_result()


# mezcla colores manualmente
class ViewBlend(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        self.model.add_event(self.update_gallery)

        self.blends = list()

        # configure grid layout
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        sidebar_frame = ctk.CTkFrame(master=self, fg_color=('gray81', 'gray20'), corner_radius=0)
        sidebar_frame.grid_rowconfigure(1, weight=1)
        sidebar_frame.grid_columnconfigure(0, weight=1)
        sidebar_frame.grid(row=0, column=0, sticky="nsew")

        self.gallery_color = GalleryColor(master=sidebar_frame, width=260,
                                          fg_color=('gray81', 'gray20'), corner_radius=0)
        self.gallery_color.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")

        self.update_gallery()

        form_frame = ctk.CTkFrame(master=sidebar_frame)
        form_frame.grid(row=2, column=0, padx=(15, 20), pady=(10, 0), sticky="nsew")

        label = ctk.CTkLabel(form_frame, text='Cantidad')
        label.grid(row=0, column=0, padx=20, pady=5)

        self.cant = CTkSpinbox(master=form_frame, from_=1, to=10)
        self.cant.set(1)
        self.cant.grid(row=0, column=1, padx=10, pady=5)

        button = ctk.CTkButton(master=sidebar_frame, text='Agregar',
                               command=self.add_color)
        button.grid(row=3, column=0, padx=20, pady=10)

        right_frame = ctk.CTkFrame(master=self, corner_radius=0, fg_color='grey92')
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=20)

        self.list_blend = ListBlend(master=right_frame, command_removed=self.removed_blend)
        self.list_blend.grid(row=0, column=0, padx=0, pady=0, sticky="nsew")

        self.result = ctk.CTkLabel(master=right_frame, text='Result',
                                   height=100, fg_color='white')
        self.result.grid(row=1, column=0, padx=0, pady=0, sticky="nsew")
        self.result_tooltip = CTkToolTip(self.result)

        save = ctk.CTkButton(master=right_frame, text='Guardar fav.', command=self.add_favorite)
        save.grid(row=2, column=0, padx=5, pady=5)

    def update_gallery(self, event_name=None):
        if (event_name == Model.evt_colors_loaded or
                event_name is None):

            self.gallery_color.remove_items()
            for color in self.model.colors:
                self.gallery_color.add_item(color)

    def removed_blend(self, index):
        print(f"item clicked: {index}")
        blend = self.blends[index]
        self.blends.remove(blend)
        self.update_result()

    def add_color(self):
        print(f"add color")
        index = self.gallery_color.get()
        if index is None:
            return
        color = self.model.colors[index]
        cant = self.cant.get()
        blend = {
            'color': color,
            'amount': cant
        }
        self.list_blend.add_item(blend)
        self.blends.append(blend)
        self.update_result()

    def update_result(self):
        color = Color(hex_=0xffffff)
        if len(self.blends) == 1:
            color = self.blends[0]['color']
        elif len(self.blends) >= 2:
            color = self.model.blend_colors(self.blends)

        color_text = get_color_label(color)
        color_str = color.get_hex()
        self.result.configure(text=color_str,
                              text_color=color_text,
                              fg_color=color_str)
        self.result_tooltip.configure(message=f'{color.rgb}\n{color_str}')

    def add_favorite(self, event=None):
        self.model.add_favorite(self.blends.copy())


# galeria de favoritos
class ViewFavorite(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        self.result_win = None
        self.blends = list()
        self.model.add_event(self.update_fav)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.list_blend = ListBlend(
            master=self, width=650, corner_radius=0,
            fg_color=('gray81', 'gray20'),
            command_removed=self.removed_blend,
            command=self.show_blend
        )
        self.list_blend.grid(row=0, column=0, padx=0, pady=0, sticky="ns")

        form_frame = ctk.CTkFrame(master=self)
        form_frame.grid(row=1, column=0, padx=(15, 20), pady=(10, 0), sticky="ew")
        form_frame.grid_columnconfigure(0, weight=1)
        form_frame.grid_rowconfigure(0, weight=1)

        bt = ctk.CTkButton(master=form_frame, text='borrar')
        bt.grid(row=0, column=0, padx=10, pady=10)

    def removed_blend(self, index):
        print(f"item clicked: {index}")
        self.model.remove_favorite(index, False)

    def update_fav(self, event_name):
        if (event_name == Model.evt_fav_added or
                event_name == Model.evt_fav_loaded):
            self.list_blend.remove_items()
            for blend in self.model.favorite:
                colors = blend['new']
                print(f'update tab favorite {colors}')
                self.list_blend.add_item(color=colors)

    def show_blend(self, index):

        blends = self.model.favorite[index]

        if sys.platform.startswith("win"):
            if self.result_win is None or not self.result_win.winfo_exists():
                self.result_win = WinResult(model=self.model, target=False)
        else:
            if self.result_win is not None or not self.result_win.winfo_exists():
                self.result_win.destroy()  # create window if its None or destroyed
            self.result_win = WinResult(model=self.model, target=False)

        self.result_win.set_data(blends)
        self.result_win.focus()


# importar exportar
class ViewExImport(View):
    def __init__(self, master, model, **kwargs):
        super().__init__(master, model, **kwargs)

        model.add_event(self.update_fav)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.form = ctk.CTkFrame(self)
        self.form.grid(padx=10, pady=10)
        self.form.grid_columnconfigure(0, weight=1)
        self.form.grid_rowconfigure(0, weight=1)

        self.add_button('Copiar Favoritos', self.copy_clipboard_favorite)
        self.add_button('Pegar Favoritos', self.past_clipboard_favorite)
        self.add_button('Copiar Colores', self.copy_clipboard_colors)
        self.add_button('Pegar Colores', self.past_clipboard_colors)

    def update_fav(self, event_name):
        for blend in self.model.favorite:
            colors = blend['new']
            print(f'update tab favorite {colors}')

    def add_button(self, text, cmd=None):
        bt = ctk.CTkButton(self.form, text=text, command=cmd)
        bt.grid(padx=10, pady=10)

    def copy_clipboard_json(self, str_json):
        self.clipboard_clear()
        self.clipboard_append(str_json)
        self.update()  # now it stays on the clipboard after the window is closed

    def copy_clipboard_colors(self):
        str_json = self.model.get_json_colors()
        print(str_json)
        self.copy_clipboard_json(str_json)

    def copy_clipboard_favorite(self):
        str_json = self.model.get_json_favorite()
        print(str_json)
        self.copy_clipboard_json(str_json)

    def past_clipboard_colors(self):
        str_json = self.clipboard_get()
        print(str_json)
        self.model.set_json_colors(str_json)

    def past_clipboard_favorite(self):
        str_json = self.clipboard_get()
        print(str_json)
        self.model.set_json_favorite(str_json)


###################################
#               Start
###################################

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        vallejo_game_color = [
            {'name': 'Bonewhite', 'value': 0xefd9a8, 'id': '72.034'},
            {'name': 'Ultra Marine Blue', 'value': 0x29397b, 'id': '72.022'},
            {'name': 'Bloody Red', 'value': 0xce0018, 'id': '72.010'},
            {'name': 'Orange Fire', 'value': 0xff7b00, 'id': '72.008'},
            {'name': 'Bronze Flesh', 'value': 0xf7944a, 'id': '72.036'},
            {'name': 'Sunblast Yellow', 'value': 0xffe700, 'id': '72.006'},
            {'name': 'Stonewall Grey', 'value': 0xb5b5b5, 'id': '72.049'},
            {'name': 'Beasty Brown', 'value': 0x663300, 'id': '72.043'},
            {'name': 'Leather Brown', 'value': 0x9c6b08, 'id': '72.040'},
            {'name': 'Dark Green', 'value': 0x005221, 'id': '72.028'},
            {'name': 'Goblin Green', 'value': 0x63b521, 'id': '72.030'},
            {'name': 'Black', 'value': 0x010101, 'id': '72.051'},
            {'name': 'White', 'value': 0xffffff, 'id': '72.001'}
        ]

        if sys.platform.startswith("win"):
            self.title("Color blend")
            self.geometry(f"{800}x{600}")
        else:  # android
            ctk.deactivate_automatic_dpi_awareness()
            ctk.set_widget_scaling(2.5)
            ctk.set_window_scaling(1.5)

        # configure grid layout
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.model = Model()
        self.model.set_data(vallejo_game_color)

        self.tabview = ctk.CTkTabview(master=self, )
        self.tabview.grid(row=0, column=0, padx=20, pady=0, sticky="nsew")

        # create tabs
        self.create_tab("Buscar Color", ViewFind)
        self.create_tab("Mezclar Color", ViewBlend)
        self.create_tab("Favoritos", ViewFavorite)
        self.create_tab("Export/Import", ViewExImport)

        self.tabview.set("Mezclar Color")  # set currently visible tab

    def create_tab(self, title, view_class):
        tab = self.tabview.add(title)
        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(0, weight=1)
        # add widgets on tab
        _frame = view_class(tab, self.model)
        _frame.grid(row=0, column=0, padx=10, pady=0, sticky="nsew")


if __name__ == "__main__":
    app = App()
    app.mainloop()
