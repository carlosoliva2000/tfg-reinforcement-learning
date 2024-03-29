from typing import Optional, Union

import gym
import numpy as np
import pygame
from pygame.rect import RectType, Rect

ANCHO = 1280
ALTO = 700


class Camara:
    def __init__(self, entidad):
        self.entidad = entidad
        self.offset = pygame.Vector2()
        self.offset_float = pygame.Vector2()
        self.limites = pygame.Vector2(-ANCHO/3, -(6*64 - (704-ALTO)))  # 444  # - 700/1.57

    def scroll(self, factor_x=16, factor_y=8):
        self.offset_float += ((self.entidad.rect.x - self.offset_float.x + self.limites.x) / factor_x,
                              (self.entidad.rect.y - self.offset_float.y + self.limites.y) / factor_y)
        self.offset.x = max(0, round(self.offset_float.x))  # Borde izquierdo
        self.offset.y = max(-64, round(self.offset_float.y))  # Borde superior
        self.offset.y = min(1964, self.offset.y)  # Borde inferior


class Juego(gym.Env):
    def __init__(self, env_config=None):
        self.nivel = Nivel()
        # self.enemigos.add(EnemigoDeambulante(pygame.Vector2(64*12, 0), self.nivel, self))
        # self.enemigos.add(EnemigoSaltarin(pygame.Vector2(64 * 14 + 32, -64*40), self.nivel, self))
        # self.enemigos.add(EnemigoTirador(pygame.Vector2(64 * 24 + 32, -64 * 40), self.nivel, self))

        self.camara: Optional[Camara] = None
        self.ventana = None
        self.flag_iniciar_render = True
        self.flag_reset = True
        self.juega_humano = False
        # 36 3**2 + 3**3

        self.action_space = gym.spaces.Discrete(7)
        self.observation_space = gym.spaces.Box(low=-1.0, high=1.0, shape=(len(self.jugador.rayos)*2+9+5,))

        self.observaciones = []
        self.observaciones_array = np.array([])

        self.done = False
        self.caida_libre = False

        self.bloque_final = 100.0
        self.x_final = self.nivel.tam_bloque * self.bloque_final  # 0.0
        self.x_checkpoint = self.nivel.tam_bloque * 1  # self.nivel.jugador.sprite.pos.x +

        self.recompensa_total = 0.0
        self.recompensa_step = 0.0
        self.recompensa_max = self.bloque_final

        self.rango_recompensa_avanzar = [0.0, 1.0]
        self.rango_recompensa_moneda = [-1.0, 1.0]
        self.rango_recompensa_dash = [-1.0, 1.5]
        self.rango_recompensa_tirador = [-1.0, 2.0]
        self.rango_recompensa_bombardeador = [-1.0, 2.0]

        self.recompensa_avanzar = 0.0
        self.recompensa_moneda = 1.0
        self.recompensa_dash = -1.0
        self.recompensa_tirador = -1.0
        self.recompensa_bombardeador = -1.0

        self.recompensa_avanzar_interp = -1.0
        self.recompensa_moneda_interp = -1.0
        self.recompensa_dash_interp = -1.0
        self.recompensa_tirador_interp = 1.0
        self.recompensa_bombardeador_interp = -1.0

        self.calcular_coeficientes_interp()

        self.step_recompensa = 0.1
        self.multiplicador = 1 / self.step_recompensa

        self.monedas_recogidas = 0
        self.monedas_max = 0

        # self.iteracion = 0
        self.id = np.random.randint(0, np.iinfo(np.int32).max)
        self.semillas = {}

        # self.acciones = {
        #     0: [0, 0, 0, 0],
        #     1: [0, 0, 0, 1],
        #     2: [0, 0, 1, 0],
        #     3: [0, 0, 1, 1],
        #     4: [0, 0, -1, 0],
        #     5: [0, 0, -1, 1],
        #     6: [0, 1, 0, 0],
        #     7: [0, 1, 0, 1],
        #     8: [0, 1, 1, 0],
        #     9: [0, 1, 1, 1],
        #     10: [0, 1, -1, 0],
        #     11: [0, 1, -1, 1],
        #     12: [1, 0, 0, 0],
        #     13: [1, 0, 0, 1],
        #     14: [1, 0, 1, 0],
        #     15: [1, 0, 1, 1],
        #     16: [1, 0, -1, 0],
        #     17: [1, 0, -1, 1],
        #     18: [1, 1, 0, 0],
        #     19: [1, 1, 0, 1],
        #     20: [1, 1, 1, 0],
        #     21: [1, 1, 1, 1],
        #     22: [1, 1, -1, 0],
        #     23: [1, 1, -1, 1],
        #     24: [-1, 0, 0, 0],
        #     25: [-1, 0, 0, 1],
        #     26: [-1, 0, 1, 0],
        #     27: [-1, 0, 1, 1],
        #     28: [-1, 0, -1, 0],
        #     29: [-1, 0, -1, 1],
        #     30: [-1, 1, 0, 0],
        #     31: [-1, 1, 0, 1],
        #     32: [-1, 1, 1, 0],
        #     33: [-1, 1, 1, 1],
        #     34: [-1, 1, -1, 0],
        #     35: [-1, 1, -1, 1],
        # }

        # Desplazamiento (-1, 0, 1), salto (0, 1), disparo (-1, 0, 1), dash(0, 1)
        self.acciones = {
            0: [0, 0, 0, 0],
            1: [1, 0, 0, 0],
            2: [-1, 0, 0, 0],
            3: [0, 1, 0, 0],
            4: [0, 0, 1, 0],
            5: [0, 0, -1, 0],
            6: [0, 0, 0, 1]
        }

        self.actualizar_coeficientes()

    @property
    def jugador(self):
        return self.nivel.jugador.sprite

    def step(self, action):
        action = self.procesar_accion(action)
        self.nivel.update()
        self.jugador.update(action)

        self.actualizar_observaciones()
        self.actualizar_recompensas()

        jugador = self.jugador
        self.done = not jugador.activo or jugador.frames_misma_pos > 600 or jugador.pos.x >= self.x_final

        # if not self.nivel.jugador.sprite.activo:
        #     print(f"Metros avanzados: {self.nivel.jugador.sprite.pos.x}")
        #     info_step = self.observaciones, self.recompensa_step, True, {}
        #     self.reset()
        #     return info_step

        return self.observaciones_array, self.recompensa_step, self.done, {}

    def render(self, mode="human"):
        if self.flag_iniciar_render:
            self.iniciar_render()

        self.ventana.fill('black')

        if self.flag_reset:
            self.camara.scroll(1, 1)
            self.flag_reset = False
        else:
            self.camara.scroll()

        self.nivel.draw(self.ventana, self.camara.offset)
        pygame.draw.line(self.ventana, 'white', (self.x_checkpoint - self.camara.offset.x, 0),
                         (self.x_checkpoint - self.camara.offset.x, 700))
        pygame.draw.line(self.ventana, 'green', (self.x_final-self.camara.offset.x, 0), (self.x_final-self.camara.offset.x, 700))


        # pygame.draw.line(self.ventana, 'red', (ANCHO/2, 0), (ANCHO/2, ALTO))
        # pygame.draw.line(self.ventana, 'red', (ANCHO / 3, 0), (ANCHO / 3, ALTO))

        pygame.display.update()

    def reset(self):
        jugador = self.jugador
        print(f"Metros avanzados: {jugador.pos.x}/{self.x_final}")
        print(f"Bloques avanzados: {jugador.pos.x/self.nivel.tam_bloque:.1f}/{self.bloque_final}")
        print(f"Coeficientes: a={self.recompensa_avanzar} m={self.recompensa_moneda} d={self.recompensa_dash} t={self.recompensa_tirador} b={self.recompensa_bombardeador}")
        print(f"Recompensa total: {self.recompensa_total}")
        print(f"Monedas recogidas: {self.monedas_recogidas}/{self.monedas_max}")
        print(f"Nivel pasado: {jugador.pos.x >= self.x_final and not self.caida_libre}\n")

        print(f"ID: {self.id}")
        self.monedas_recogidas = 0

        if self.semillas.get(self.nivel.semilla):
            self.semillas[self.nivel.semilla] += 1
        else:
            self.semillas[self.nivel.semilla] = 1

        # self.iteracion += 1
        # if self.iteracion % 100 == 0:
        #     with open(f"Semillas{self.id}.txt", 'w') as f:
        #         f.write(str(self.semillas))

        self.caida_libre = False
        self.flag_reset = True
        self.recompensa_total = 0
        self.recompensa_step = 0
        self.actualizar_coeficientes()
        self.nivel.reset()

        self.monedas_max = 0
        for m in self.nivel.chunks["monedas"][0]:
            if m.pos.x < self.bloque_final * self.nivel.tam_bloque:
                self.monedas_max += 1
        self.recompensa_max = self.monedas_max
        # print("Monedas max", self.monedas_max)
        # print("Monedas chunk", len(self.nivel.chunks["monedas"][0]))

        # self.enemigos.add(EnemigoDeambulante(pygame.Vector2(64*12, 0), self.nivel, self))
        # self.enemigos.add(EnemigoSaltarin(pygame.Vector2(64 * 14 + 32, -64*40), self.nivel, self))
        # self.enemigos.add(EnemigoTirador(pygame.Vector2(64 * 24 + 32, -64 * 40), self.nivel, self))

        self.actualizar_observaciones()

        self.x_checkpoint = self.nivel.tam_bloque * 1

        return self.observaciones_array

    # def close(self):
    #     super().close()
    #     with open(f"Semillas{self.id}.txt", 'w') as f:
    #         f.write(str(self.semillas))

    def iniciar_render(self):
        self.flag_iniciar_render = False

        pygame.init()
        self.ventana = pygame.display.set_mode((1280, 700))
        self.camara = Camara(self.nivel.jugador.sprite)

    def actualizar_observaciones(self):
        self.observaciones.clear()
        j = self.nivel.jugador.sprite
        for r in j.rayos:
            self.observaciones.append(r.longitud_interp)
            self.observaciones.append(r.objeto_impactado_interp)
        self.observaciones.append(np.interp(j.velocidad.x, [-Jugador.VELOCIDAD_DASH, Jugador.VELOCIDAD_DASH], [-1.0, 1.0]))
        self.observaciones.append(np.interp(j.velocidad.y if not j.en_suelo else 0.0, [Jugador.VELOCIDAD_SALTO, 0, Jugador.VELOCIDAD_TERMINAL], [-1.0, 0.0, 1.0]))
        self.observaciones.append(float(j.orientacion))
        self.observaciones.append(np.interp(j.pos.x, [0.0, self.x_final], [-1.0, 1.0]))
        # self.observaciones.append(np.interp(self.x_checkpoint - j.pos.x, [0, 64, 64*3], [1.0, 0.0, -1.0]))  # 64 * 6 = 384, 384 * 3
        self.observaciones.append(1.0 if j.puede_saltar else -1.0)
        self.observaciones.append(1.0 if j.puede_doble_saltar else -1.0)
        self.observaciones.append(1.0 if j.puede_disparar else -1.0)
        self.observaciones.append(1.0 if j.puede_dashear else -1.0)
        self.observaciones.append(1.0 if j.animacion_activa else -1.0)
        self.observaciones.append(self.recompensa_avanzar_interp)
        self.observaciones.append(self.recompensa_moneda_interp)
        self.observaciones.append(self.recompensa_dash_interp)
        self.observaciones.append(self.recompensa_tirador_interp)
        self.observaciones.append(self.recompensa_bombardeador_interp)

        self.observaciones_array = np.array(self.observaciones)

    def actualizar_recompensas(self):
        self.recompensa_step = 0.0
        jugador = self.jugador

        # Caer al vacío
        caida_libre = True
        for r in jugador.rayos:
            if r.rayo_bajo and (r.objeto_impactado == 1 or r.objeto_impactado == 2 or r.objeto_impactado == 5):
                caida_libre = False
                break
        self.caida_libre = caida_libre

        # RECOMPENSAS
        # Avanzar 64 * 6 metros recompensa 1.0 puntos
        if jugador.pos.x >= self.x_checkpoint and not caida_libre:
            # self.x_checkpoint = jugador.pos.x + self.nivel.tam_bloque * 1  # 6
            self.x_checkpoint += self.nivel.tam_bloque * 1  # 6
            self.recompensa_step += self.recompensa_avanzar

        # if jugador.pos.x >= self.x_final and not caida_libre:
        #     self.recompensa_step += 5.0

        # if caida_libre:
        #     self.recompensa_step = -0.1

        # Recoger una moneda recompensa 1 por moneda
        self.monedas_recogidas += jugador.monedas_recogidas_frame
        if jugador.monedas_recogidas_frame:
            self.recompensa_step += self.recompensa_moneda

        # Matar a un enemigo haciendo (de cualquier manera) recompensa con 5 puntos
        if jugador.asesinatos_dash_frame:
            self.recompensa_step += self.recompensa_dash
        if jugador.asesinatos_tiro_horizontal_frame:
            jugador.asesinatos_tiro_horizontal_frame = 0
            self.recompensa_step += self.recompensa_tirador
        if jugador.asesinatos_tiro_vertical_frame:
            jugador.asesinatos_tiro_vertical_frame = 0
            self.recompensa_step += self.recompensa_bombardeador


        # PENALIZACIONES
        # # Disparar sin ningún motivo (no hay enemigos a la vista)
        # enemigos_en_vista = False
        # if jugador.ha_disparado:
        #     for r in jugador.rayos:
        #         if r.objeto_impactado == 3 or r.objeto_impactado == 4:
        #             enemigos_en_vista = True
        #             break
        #     if not enemigos_en_vista:
        #         self.recompensa_step -= 0.5
        #
        # # Caer al vacío
        # caida_libre = True
        # for r in jugador.rayos:
        #     if r.rayo_bajo and (r.objeto_impactado == 1 or r.objeto_impactado == 2 or r.objeto_impactado == 5):
        #         caida_libre = False
        #         break
        # if caida_libre:
        #     self.recompensa_step -= 0.5

        # Morir por un disparo enemigo penaliza 5 puntos
        if jugador.disparado:
            self.recompensa_step = -1.0

        # Morir por contacto con un enemigo penaliza 10 puntos
        if jugador.asesinado:
            self.recompensa_step = -1.0

        # Morir por caída o por pisar pinchos penaliza 20 puntos
        if jugador.fuera_limites or jugador.pinchado:
            self.recompensa_step = -1.0

        if jugador.frames_misma_pos > 600:
            self.recompensa_step = -1.0

        self.recompensa_total += self.recompensa_step

    def procesar_accion(self, accion):
        return accion if self.juega_humano else self.acciones[accion]

    def actualizar_coeficientes(self):
        self.recompensa_avanzar = self.actualizar_coeficiente(self.rango_recompensa_avanzar)
        self.recompensa_moneda = self.actualizar_coeficiente(self.rango_recompensa_moneda)
        self.recompensa_dash = self.actualizar_coeficiente(self.rango_recompensa_dash)
        self.recompensa_tirador = self.actualizar_coeficiente(self.rango_recompensa_tirador)
        self.recompensa_bombardeador = self.actualizar_coeficiente(self.rango_recompensa_bombardeador)
        self.calcular_coeficientes_interp()

    def actualizar_coeficiente(self, rango: list) -> float:
        inf, sup = rango[0], rango[1]
        return np.random.randint(inf*self.multiplicador, sup*self.multiplicador+1)/self.multiplicador

    def calcular_coeficientes_interp(self):
        self.recompensa_avanzar_interp = np.interp(self.recompensa_avanzar, self.rango_recompensa_avanzar, [-1.0, 1.0])
        self.recompensa_moneda_interp = np.interp(self.recompensa_moneda, self.rango_recompensa_moneda, [-1.0, 1.0])
        self.recompensa_dash_interp = np.interp(self.recompensa_dash, self.rango_recompensa_dash, [-1.0, 1.0])
        self.recompensa_tirador_interp = np.interp(self.recompensa_tirador, self.rango_recompensa_tirador, [-1.0, 1.0])
        self.recompensa_bombardeador_interp = np.interp(self.recompensa_bombardeador,
                                                        self.rango_recompensa_bombardeador, [-1.0, 1.0])

class Nivel:
    def __init__(self):
        self.chunks = {
            "bloques": [],
            "pinchos": [],
            "monedas": [],
            "enemigos": []
        }
        self.bloques = SpatialHash()  # pygame.sprite.Group()
        self.pinchos = SpatialHash()
        self.monedas = SpatialHash()
        self.enemigos = SpatialHash()
        self.disparos = SpatialHash()
        self.jugador = SpatialHashSingle(Jugador(pygame.Vector2(64, 0), self))  # 64, 398

        self.tam_bloque = 64
        self.max_y = 40
        self.min_y = 3
        self.trigger_vacio = (self.max_y+2)*self.tam_bloque

        self.ultima_x = 0
        self.ultima_y = 0
        self.step_generacion = 20 * self.tam_bloque

        self.datos_nivel = []

        self.zona_seguridad = self.tam_bloque * 4

        self.semilla = 0

        self.repeticiones_en_y = 0

        self.reset()

    def generar_nivel(self):
        def coinciden_bloques(s: Sprite, g: list[Sprite]) -> bool:
            for s2 in g:
                if pygame.sprite.collide_rect(s, s2):
                    return True
            return False

        tam_bloque = 64
        y_min, y_max = self.min_y, self.max_y
        y_actual = self.ultima_y

        max_ancho_plat = 10
        min_ancho_plat = 2
        ancho_plataforma = np.random.randint(min_ancho_plat, max_ancho_plat)
        bloques_restantes = ancho_plataforma
        inc_altura = 4
        dec_altura = 4

        bloques = []
        pinchos = []
        monedas = []
        enemigos = []

        for x in range(self.ultima_x, self.ultima_x + self.step_generacion + 0, tam_bloque):
            # x = x * tam_bloque
            if np.random.random() < 0.9 or x <= self.zona_seguridad:  # 80% de suelo, 20% de vacío
                if bloques_restantes <= 0:
                    y_actual = np.clip(np.random.randint(y_actual - inc_altura, y_actual + dec_altura + 1), y_min, y_max)  # 8 * tam_bloque
                    if y_actual == self.ultima_y:
                        self.repeticiones_en_y += 1
                    else:
                        self.repeticiones_en_y = 0

                    if self.repeticiones_en_y == 1:  # return 1 if random.random() < 0.5 else -1
                        if np.random.random() < 0.5:  # Bajada
                            y_actual = np.clip(y_actual - np.random.randint(1, inc_altura + 1), y_min, y_max)
                        else:  # Subida
                            y_actual = np.clip(y_actual + np.random.randint(1, dec_altura + 1), y_min, y_max)
                        self.repeticiones_en_y = 0

                    ancho_plataforma = np.random.randint(min_ancho_plat, max_ancho_plat)
                    bloques_restantes = ancho_plataforma

                bloque = Bloque(pygame.Vector2(x, y_actual * tam_bloque), tam_bloque + 1)
                if not coinciden_bloques(bloque, monedas):
                    bloques.append(bloque)
                    self.bloques.add(bloque)

                if np.random.random() < 0.05 and x > self.zona_seguridad:
                    enemigo = EnemigoSaltarin(pygame.Vector2(bloque.rect.centerx, bloque.rect.top - EnemigoSaltarin.DIMENSION[1]), self, 1 if np.random.random() < 0.5 else -1)
                    enemigos.append(enemigo)
                    self.enemigos.add(enemigo)
                if np.random.random() < 0.025 and x > self.zona_seguridad:
                    enemigo = EnemigoTirador(pygame.Vector2(bloque.rect.centerx, bloque.rect.top - EnemigoTirador.DIMENSION[1]), self, 1 if np.random.random() < 0.5 else -1)
                    enemigos.append(enemigo)
                    self.enemigos.add(enemigo)

                if np.random.random() < 0.1 and x > self.zona_seguridad:
                    pincho = Pinchos(pygame.Vector2(x, y_actual*tam_bloque), tam_bloque+1)
                    pinchos.append(pincho)
                    self.pinchos.add(pincho)

            for y in range(np.random.randint(1, 4)):
                if np.random.random() < 0.05:
                    moneda = Moneda(pygame.Vector2(x + tam_bloque / 2 - Moneda.TAM / 2,
                                                           (y_actual-y) * tam_bloque - tam_bloque / 2 - Moneda.TAM / 2))
                    if not coinciden_bloques(moneda, bloques):
                        monedas.append(moneda)
                        self.monedas.add(moneda)
            if np.random.random() < 0.05:
                y_plat = np.clip(np.random.randint(y_actual - dec_altura, y_actual - 3 + 1), y_min, y_max)
                anchura = np.random.randint(3, 6)
                for i in range(1, anchura):
                    bloque = Bloque(pygame.Vector2(x+i*tam_bloque, y_plat * tam_bloque), tam_bloque + 1)  # 'yellow'
                    if not coinciden_bloques(bloque, monedas):
                        bloques.append(bloque)
                        self.bloques.add(bloque)
                    for y in range(np.random.randint(1, 4)):
                        if np.random.random() < 0.5:
                            moneda = Moneda(pygame.Vector2((x+i*tam_bloque)+tam_bloque/2-Moneda.TAM/2, (y_plat-y)*tam_bloque-tam_bloque/2-Moneda.TAM/2))
                            if not coinciden_bloques(moneda, bloques):
                                monedas.append(moneda)
                                self.monedas.add(moneda)

            self.ultima_y = y_actual
            bloques_restantes -= 1
        self.chunks["bloques"].append(bloques)
        self.chunks["pinchos"].append(pinchos)
        self.chunks["monedas"].append(monedas)
        self.chunks["enemigos"].append(enemigos)
        self.ultima_x += self.step_generacion

    def update(self):
        self.disparos.update()
        self.enemigos.update()
        x_jugador = self.jugador.sprite.pos.x
        if self.ultima_x - x_jugador < 64 * 20:
            self.generar_nivel()
            if len(self.chunks["bloques"]) > 4:
                bloques = self.chunks["bloques"].pop(0)
                self.bloques.remove(bloques)

                pinchos = self.chunks["pinchos"].pop(0)
                self.pinchos.remove(pinchos)

                monedas = self.chunks["monedas"].pop(0)
                self.monedas.remove(monedas)

                enemigos = self.chunks["enemigos"].pop(0)
                self.enemigos.remove(enemigos)

    def reset(self):
        self.chunks["bloques"].clear()
        self.chunks["pinchos"].clear()
        self.chunks["monedas"].clear()
        self.chunks["enemigos"].clear()
        self.bloques.empty()  # = SpatialHash()  # pygame.sprite.Group()
        self.pinchos.empty()  # = SpatialHash()
        self.monedas.empty()  # = SpatialHash()
        self.enemigos.empty()  # = SpatialHash()
        self.disparos.empty()  # = SpatialHash()

        semilla = np.random.randint(0, np.iinfo(np.int32).max)  # 2010757495  1641465674
        # semilla = 664581131   514453980  2013199340
        print(f"Semilla: {semilla}")
        np.random.seed(semilla)
        self.semilla = semilla

        # datos_nivel = [
        #     "                         ",
        #     "        X              XX",
        #     "                        X",
        #     "                XXX     X",
        #     "            X           X",
        #     "    XXXXX              X",
        #     "                     XX",
        #     "                    X",
        #     "XXXXX  XXXXX    XXXX",
        #     "XXX XXXXXXXX  XXXXXX",
        #     "XX XXXXXXXXX  XXXXXX"
        # ]
        #
        # datos_nivel = [
        #     "        X    ...       XX.",
        #     "             ...       .X.",
        #     "                XXX     X",
        #     "     ...    X           X",
        #     "    XXXXX              X",
        #     "             .       XX",
        #     "             .      X",
        #     "XXXXX  XXXX    XX  X",
        #     "XXX.XX         X  XX",
        #     "XX      XXXX.     XX",
        #     "XXXXXXXXXXXX. XXXXXX"
        # ]
        #
        # datos_nivel = [
        #     "        X    ...       XX.",
        #     "             ...       .X.",
        #     "X               XXX     X",
        #     "X    ...    X           X",
        #     " X  XXXXX              X",
        #     "  X          .       XX",
        #     "   X         .      X",
        #     "XXXXX  XXXX  XXXXXXX",
        #     "XXX.XX      X  X  XX",
        #     "XX      XXXX.     XX",
        #     "XXXXXXXXXXXX. XXXXXX"
        # ]

        # for fila_i, fila in enumerate(datos_nivel):
        #     for col_i, celda in enumerate(fila):
        #         x = col_i * tam_bloque
        #         y = fila_i * tam_bloque
        #         if celda == 'X':
        #             self.bloques.add(Bloque(pygame.Vector2(x, y), tam_bloque+1))  # tam+1 para evitar huecos de 1 px
        #         elif celda == '.':
        #             self.monedas.add(Moneda(pygame.Vector2(x+tam_bloque/2-Moneda.TAM/2, y+tam_bloque/2-Moneda.TAM/2)))
        #         # elif celda == 'P':
        #         #     print(x, y)
        #         #     self.jugador.add(Jugador((x, y)))

        self.ultima_x = 0
        self.ultima_y = np.random.randint(self.min_y, self.max_y)
        print(f"Altura inicial: {self.ultima_y}")

        self.generar_nivel()
        # self.generar_nivel()

        bloque_seguro = self.chunks["bloques"][0][0]

        jugador = self.jugador.sprite
        jugador.pos.update(bloque_seguro.rect.centerx, bloque_seguro.rect.top-jugador.DIMENSION[1])
        jugador.rect.x = round(jugador.pos.x)  # bloque_seguro.rect.centerx
        jugador.rect.y = round(jugador.pos.y)  # bloque_seguro.rect.top  bottom
        self.jugador.sprite.reset()
        # self.datos_nivel = datos_nivel
        # self.tam_bloque = tam_bloque

        # self.monedas.empty()
        # for fila_i, fila in enumerate(datos_nivel):
        #     for col_i, celda in enumerate(fila):
        #         if celda == '.':
        #             x = col_i * tam_bloque
        #             y = fila_i * tam_bloque
        #             self.monedas.add(Moneda(pygame.Vector2(x+tam_bloque/2-Moneda.TAM/2, y+tam_bloque/2-Moneda.TAM/2)))

    def draw(self, ventana, offset):
        self.disparos.draw(ventana, offset)
        self.enemigos.draw(ventana, offset)

        self.bloques.draw(ventana, offset)
        self.pinchos.draw(ventana, offset)
        self.monedas.draw(ventana, offset)

        if self.jugador.sprite.activo:
            self.jugador.draw(ventana, offset)
            for r in self.jugador.sprite.rayos:
                r.render(ventana, offset)


class Sprite(pygame.sprite.Sprite):
    def __init__(self,
                 pos: pygame.Vector2,
                 dim: tuple,
                 color):
        super().__init__()

        self.image = pygame.Surface(dim)
        self.image.fill(color)
        self.rect = self.image.get_rect(topleft=pos)

        self.pos = pos
        self.activo = True

    def kill(self) -> None:
        super().kill()
        self.activo = False

    def reset(self):
        self.activo = True


class Bloque(Sprite):
    COLOR = 'grey'

    def __init__(self, pos: pygame.Vector2, tam, color=COLOR):
        super().__init__(pos, (tam, tam), color)


class Pinchos(Bloque):
    COLOR = 'red'

    def __init__(self, pos: pygame.Vector2, tam):
        super().__init__(pos, tam, self.COLOR)


class Moneda(Sprite):
    TAM = 16
    DIMENSION = (TAM, TAM)
    COLOR = 'yellow'

    def __init__(self, pos: pygame.Vector2):
        super().__init__(pos, self.DIMENSION, self.COLOR)


class Entidad(Sprite):
    GRAVEDAD = 0.4
    VELOCIDAD_SALTO = -7
    VELOCIDAD_TERMINAL = 50

    def __init__(self,
                 pos: pygame.Vector2,
                 dim: tuple,
                 color,
                 orientacion: int,
                 nivel: Nivel,
                 velocidad_x=4,
                 accion_por_defecto=None):
        super().__init__(pos, dim, color)
        self.nivel = nivel
        self.velocidad = pygame.Vector2()
        self.velocidad_x = velocidad_x
        self.accion_por_defecto = accion_por_defecto

        # Inputs de accciones
        self.input_mover = 0
        self.input_saltar = 0

        # Acción que realiza una Entidad en un instante
        self.accion = None

        # Indica la orientación horizontal, 1 si mira hacia la derecha o -1 si mira hacia la izquierda
        self.orientacion = orientacion
        self.orientacion_original = orientacion

        # Le afecta la gravedad, por lo que cae en función de la velocidad cada actualización
        self.afectado_por_gravedad = True

        # Flag que indica si hay colisión horizontal en esta actualización
        self.flag_colision_horizontal = False

        # Flag que indica si hay colisión vertical en esta actualización
        self.flag_colision_vertical = False

        # Indica si la entidad se encuentra apoyada en el suelo
        self.en_suelo = False

        # Indica si la entidad ha colisionado alguna vez con otro sprite, ayudando a la detección del flag anterior
        self.ha_colisionado = False

        # Indica si la entidad debería comprobar colisiones horizontales
        self.comprobar_colisiones_horizontales = True

        # Indica si la entidad debería comprobar colisiones verticales
        self.comprobar_colisiones_verticales = True

        # Indica si el sistema de detección de colisiones es discreto (True) o contínuo (False) (POR IMPLEMENTAR)
        self.deteccion_colisiones_discreta = True

        # Indica si la entidad está realizando un salto
        self.saltando = False

        # Indica si la entidad está cayendo (preferible a consultar velocidad.y)
        self.cayendo = False

        # Indica si existe alguna animación activa en este instante
        self.animacion_activa = False

        self.cooldown_salto = 20

        self.timer_salto = 0

        self.puede_saltar = False

        self.asesinado = False
        self.disparado = False
        self.pinchado = False
        self.fuera_limites = False

    def reset(self):
        super().reset()

        self.velocidad = pygame.Vector2()

        # Inputs de accciones
        self.input_mover = 0
        self.input_saltar = 0

        # Acción que realiza una Entidad en un instante
        self.accion = None

        # Indica la orientación horizontal, 1 si mira hacia la derecha o -1 si mira hacia la izquierda
        self.orientacion = self.orientacion_original

        # Flag que indica si hay colisión horizontal en esta actualización
        self.flag_colision_horizontal = False

        # Flag que indica si hay colisión vertical en esta actualización
        self.flag_colision_vertical = False

        # Indica si la entidad se encuentra apoyada en el suelo
        self.en_suelo = False

        # Indica si la entidad ha colisionado alguna vez con otro sprite, ayudando a la detección del flag anterior
        self.ha_colisionado = False

        # Indica si la entidad está realizando un salto
        self.saltando = False

        # Indica si la entidad está cayendo (preferible a consultar velocidad.y)
        self.cayendo = False

        # Indica si existe alguna animación activa en este instante
        self.animacion_activa = False

        self.timer_salto = 0

        self.asesinado = False
        self.disparado = False
        self.pinchado = False
        self.fuera_limites = False

    def update(self, accion=None):
        if self.pos.y > self.nivel.trigger_vacio:  # 1000
            self.fuera_limites = True
            self.kill()

        if self.activo:
            self.seleccionar_accion(accion)
            accion = self.accion

            self.manejar_input_acciones(accion)
            self.aplicar_acciones()
            self.actualizar_flags()
            self.actualizar_timers()
            self.resolver_flags_y_timers()
            self.actualizar_animacion()
            self.log()

    def seleccionar_accion(self, accion):
        if accion:
            self.accion = accion
        elif self.accion_por_defecto:
            self.accion = self.accion_por_defecto
        else:
            # IA de los enemigos (determinar acción según la situación)
            self.accion = self.determinar_accion()

    def determinar_accion(self):
        return self.accion

    def manejar_input_acciones(self, accion):
        self.input_mover = accion[0]
        self.input_saltar = accion[1]

    def aplicar_acciones(self):
        self.aplicar_movimiento_horizontal()
        self.pos.x += self.velocidad.x
        self.rect.x = round(self.pos.x)
        if self.comprobar_colisiones_horizontales:
            self.calcular_colisiones_horizontales()

        self.aplicar_movimiento_vertical()
        self.pos.y += self.velocidad.y
        self.rect.y = round(self.pos.y)
        if self.comprobar_colisiones_verticales:
            self.calcular_colisiones_verticales()

    def actualizar_flags(self):
        self.cayendo = round(self.velocidad.y) > 0
        self.ha_colisionado = (self.ha_colisionado or
                               self.flag_colision_horizontal or self.flag_colision_vertical)

        # Si la gravedad no afecta y se produce una colisión horizontal, producirá falsos positivos
        if self.ha_colisionado:
            self.en_suelo = not self.cayendo and not self.saltando
        else:
            self.en_suelo = False

        self.puede_saltar = self.en_suelo and not self.saltando

    def actualizar_timers(self):
        if self.timer_salto > 0 and self.saltando:
            self.timer_salto -= 1

    def resolver_flags_y_timers(self):
        pass

    def actualizar_animacion(self):
        pass

    def log(self):
        pass

    def aplicar_movimiento_horizontal(self):
        self.mover()

    def aplicar_movimiento_vertical(self):
        self.saltar()
        if self.afectado_por_gravedad:
            self.aplicar_gravedad()

        if self.velocidad.y > self.VELOCIDAD_TERMINAL:
            self.velocidad.y = self.VELOCIDAD_TERMINAL

    def mover(self):
        accion = self.input_mover
        if not self.animacion_activa:
            if accion:
                self.orientacion = 1 if accion == 1 else -1
            self.velocidad.x = accion * self.velocidad_x

    def saltar(self):
        accion = self.input_saltar
        if accion and self.en_suelo:
            self.velocidad.y = self.VELOCIDAD_SALTO
            self.saltando = True
            self.timer_salto = self.cooldown_salto

    def aplicar_gravedad(self):
        self.velocidad.y += self.GRAVEDAD

    def calcular_colisiones_horizontales(self, objs_colision=None):
        if objs_colision is None:
            objs_colision = self.nivel.bloques
        colisiones = 0
        for bloque in objs_colision:
            if self.rect.colliderect(bloque.rect):
                colisiones += 1
                self.en_colision_horizontal(bloque, self.velocidad.x)

            self.flag_colision_horizontal = colisiones > 0

    def calcular_colisiones_verticales(self, objs_colision=None):
        if objs_colision is None:
            objs_colision = self.nivel.bloques
        colisiones = 0
        for bloque in objs_colision:
            if self.rect.colliderect(bloque.rect):
                colisiones += 1
                self.en_colision_vertical(bloque, self.velocidad.y)

        self.flag_colision_vertical = colisiones > 0

    def en_colision_horizontal(self, obj, vx):
        if self.velocidad.x > 0:
            self.rect.right = obj.rect.left
        elif self.velocidad.x < 0:
            self.rect.left = obj.rect.right

        self.pos.x = self.rect.x

    def en_colision_vertical(self, obj, vy):
        if self.velocidad.y > 0:
            self.rect.bottom = obj.rect.top
            self.saltando = False
        elif self.velocidad.y < 0:
            self.rect.top = obj.rect.bottom

        self.pos.y = self.rect.y
        self.velocidad.y = 0
        # if self.velocidad.y > 0:
        #     self.rect.bottom = bloque.rect.top
        #     self.pos.y = self.rect.y
        #     self.velocidad.y = 0
        #     self.saltando = False
        #     self.doble_salto = False
        # elif self.velocidad.y < 0:
        #     self.rect.top = bloque.rect.bottom
        #     self.pos.y = self.rect.y
        #     self.velocidad.y = 0


class Tirador(Entidad):
    def __init__(self, pos: pygame.Vector2, dim: tuple, color, orientacion: int, nivel: Nivel, vel_x):
        super().__init__(pos, dim, color, orientacion, nivel, vel_x)

        self.input_disparar = 0

        self.cooldown_disparo = 20
        self.timer_disparo = 0

        self.ha_disparado = False
        self.puede_disparar = False

    def manejar_input_acciones(self, accion):
        super().manejar_input_acciones(accion)
        self.input_disparar = accion[2]

    def aplicar_acciones(self):
        super().aplicar_acciones()
        self.disparar()

    def actualizar_flags(self):
        super().actualizar_flags()
        self.ha_disparado = self.timer_disparo == self.cooldown_disparo and self.input_disparar
        self.puede_disparar = self.timer_disparo <= 1

    def actualizar_timers(self):
        super().actualizar_timers()
        if self.timer_disparo > 0:
            self.timer_disparo -= 1

    def disparar(self):
        if self.timer_disparo == 0:
            if self.input_disparar == 1:
                # print("PUM")
                self.timer_disparo = self.cooldown_disparo
                self.nivel.disparos.add(Disparo(self.rect, self.velocidad, self.orientacion, self.groups()[0], self.nivel))
            elif self.input_disparar == -1:
                self.timer_disparo = self.cooldown_disparo
                self.nivel.disparos.add(Disparo(self.rect, self.velocidad, Disparo.ORIENTACION_ABAJO, self.groups()[0], self.nivel))


class Jugador(Tirador):
    DIMENSION = (32, 50)
    COLOR = 'red'
    ORIENTACION_INICIAL = 1
    VELOCIDAD_SALTO = -14  # -14
    VELOCIDAD_DOBLE_SALTO = int(VELOCIDAD_SALTO * 0.75)
    VELOCIDAD_X = 4
    VELOCIDAD_DASH = 15

    def __init__(self, pos: pygame.Vector2, nivel: Nivel):
        super().__init__(pos, self.DIMENSION, self.COLOR, self.ORIENTACION_INICIAL, nivel, self.VELOCIDAD_X)

        # Inputs de accciones
        self.input_dash = 0

        # Indica si la entidad está realizando un doble salto
        self.doble_salto = False

        # Indica si la animación de dash se ha iniciado
        self.dash_iniciado = False

        # Indica si la animación de dash ha finalizado
        self.dash_finalizado = False

        self.cooldown_dash = 60*1
        # TODO: ajustar duración y velocidad de dash. Es muy corto y mantiene demasiada inercia
        self.duracion_dash = 10  # 10

        self.timer_cooldown_dash = 0
        self.timer_duracion_dash = 0

        self.rayos = [Rayo(self, ang) for ang in np.linspace(0, 2*np.pi, 17)]
        # self.rayos.extend([Rayo(self, ang) for ang in np.linspace(-np.pi/2, np.pi/2, 19)])
        # self.rayos.extend([Rayo(self, ang) for ang in np.linspace(3*np.pi/2, np.pi/2, 19)])
        # self.rayos = [Rayo(self, ang) for ang in np.linspace(-np.pi/2, np.pi/2, 9)]

        self.asesinatos_dash_frame = 0
        self.asesinatos_tiro_horizontal_frame = 0
        self.asesinatos_tiro_vertical_frame = 0
        self.monedas_recogidas_frame = 0

        self.en_suelo = True
        self.puede_saltar = self.puede_disparar = True
        self.puede_doble_saltar = self.puede_dashear = True

        self.ultima_x = pos.x
        self.frames_misma_pos = 0

    def kill(self) -> None:
        self.activo = False

    def reset(self):
        super().reset()

        self.doble_salto = False
        self.dash_iniciado = False
        self.dash_finalizado = False
        self.timer_cooldown_dash = 0
        self.timer_duracion_dash = 0
        self.asesinatos_dash_frame = 0
        self.asesinatos_tiro_horizontal_frame = 0
        self.asesinatos_tiro_vertical_frame = 0
        self.monedas_recogidas_frame = 0
        self.en_suelo = True
        self.puede_saltar = self.puede_disparar = self.puede_dashear = True
        self.puede_doble_saltar = False
        self.ultima_x = self.pos.x
        self.frames_misma_pos = 0

        for r in self.rayos:
            r.reset()

    def update(self, accion=None):
        self.asesinatos_dash_frame = 0
        self.monedas_recogidas_frame = 0
        super().update(accion)
        for r in self.rayos:
            r.actualizar()

    def manejar_input_acciones(self, accion):
        super().manejar_input_acciones(accion)
        self.input_dash = accion[3]

    def actualizar_flags(self):
        super().actualizar_flags()
        self.puede_doble_saltar = self.saltando and not self.doble_salto
        self.puede_dashear = not self.dash_iniciado and self.timer_cooldown_dash <= 1
        self.puede_disparar = self.puede_disparar and not self.dash_iniciado

        if abs(self.pos.x - self.ultima_x) < self.velocidad_x:
            self.frames_misma_pos += 1
        else:
            self.frames_misma_pos = 0
        self.ultima_x = self.pos.x

    def actualizar_timers(self):
        super().actualizar_timers()
        if self.timer_cooldown_dash > 0:
            self.timer_cooldown_dash -= 1

        if self.timer_duracion_dash > 0:
            self.timer_duracion_dash -= 1
            if self.timer_duracion_dash == 0:
                self.dash_finalizado = True

    # def resolver_flags_y_timers(self):
    #     # Escalar
    #     if self.flag_colision_horizontal and self.cayendo and not self.doble_salto:
    #         # Fenómeno curioso: esto tiende una velocidad de 0,8
    #         # Llego a la conclusión de que un número n dividido entre 2 más un número m
    #         # repetidamente tiende a 2m.
    #         # n/2 + m -> 2m
    #         # Por ejemplo: n/2 + 0,4 -> 0,8
    #         self.velocidad.y /= 2

    def actualizar_animacion(self):
        self.image.fill(self.COLOR if not self.dash_iniciado else 'white')
        self.image.fill('DARKRED',
                        pygame.rect.Rect(self.rect.w/2 if self.orientacion == 1 else 0,
                                         self.rect.h/6, self.rect.w/2+1, self.rect.h/6))

    def aplicar_movimiento_horizontal(self):
        super().aplicar_movimiento_horizontal()
        self.dashear()

    def saltar(self):
        accion = self.input_saltar
        if accion and (self.en_suelo or self.saltando):  # (not self.cayendo or self.saltando)
            if not self.saltando:
                self.velocidad.y = self.VELOCIDAD_SALTO
                self.saltando = True
                self.timer_salto = self.cooldown_salto
            elif not self.doble_salto and not self.timer_salto:
                self.velocidad.y = self.VELOCIDAD_DOBLE_SALTO
                self.doble_salto = True

    def disparar(self):
        if not self.dash_iniciado:
            super().disparar()

    def dashear(self):
        accion = self.input_dash
        if accion and not self.dash_iniciado and self.timer_cooldown_dash == 0:
            # print("Inicio dash...")
            self.dash_iniciado = True
            self.dash_finalizado = False
            self.timer_duracion_dash = self.duracion_dash
            self.animacion_activa = True

        if self.dash_iniciado and not self.dash_finalizado:
            # print("DASH!")
            self.velocidad.x = self.VELOCIDAD_DASH * self.orientacion  # 15
            self.velocidad.y = 0
        elif self.dash_iniciado and self.dash_finalizado:
            # print("Finalizo dash\n")
            self.velocidad.x = 0
            self.timer_cooldown_dash = self.cooldown_dash
            self.dash_iniciado = False
            self.dash_finalizado = False
            self.animacion_activa = False

    def calcular_colisiones_horizontales(self, objs_colision=None):
        super().calcular_colisiones_horizontales()
        moneda = pygame.sprite.spritecollideany(self, self.nivel.monedas)
        if moneda:
            self.monedas_recogidas_frame += 1
            moneda.kill()

        enemigo = pygame.sprite.spritecollideany(self, self.nivel.enemigos)
        if enemigo:
            if self.dash_iniciado:
                self.asesinatos_dash_frame += 1
                enemigo.kill()
            else:
                self.asesinado = True
                self.kill()

    def calcular_colisiones_verticales(self, objs_colision=None):
        super().calcular_colisiones_verticales(self.nivel.pinchos)
        super().calcular_colisiones_verticales()

    def en_colision_vertical(self, obj, vy):
        super().en_colision_vertical(obj, vy)
        if vy > 0:
            self.doble_salto = False
            if isinstance(obj, Pinchos):
                self.pinchado = True
                self.kill()


class EnemigoDeambulante(Entidad):
    VELOCIDAD_SALTO = -9
    COLOR = 'brown'
    DIMENSION = (50, 30)

    def __init__(self, pos: pygame.Vector2, nivel: Nivel):
        super().__init__(pos, self.DIMENSION, self.COLOR, -1, nivel, 1)

    def determinar_accion(self):
        if self.flag_colision_horizontal:
            return [-self.orientacion, 0]
        else:
            return [self.orientacion, 0]

    def actualizar_animacion(self):
        self.image.fill(self.COLOR)
        self.image.fill('black',
                        pygame.rect.Rect(self.rect.w-self.rect.w/3 if self.orientacion == 1 else 0,
                                         self.rect.h/6, self.rect.w/3+1, self.rect.h/6))


class EnemigoSaltarin(Entidad):
    VELOCIDAD_SALTO = -9
    COLOR = 'darkred'
    DIMENSION = (50, 30)

    def __init__(self, pos: pygame.Vector2, nivel: Nivel, orientacion=-1):
        super().__init__(pos, self.DIMENSION, self.COLOR, orientacion, nivel, 1)
        self.prev_x = self.pos.x
        self.intentar_salto = False

    def determinar_accion(self):
        if self.flag_colision_horizontal and self.en_suelo:
            if not self.intentar_salto or self.prev_x != self.pos.x:
                self.intentar_salto = True
                self.prev_x = self.pos.x
                # self.velocidad_x = 4  # Ajusta velocidad para saltar
                return [self.orientacion, 1]
            else:
                # if self.prev_x == self.pos.x:
                return [-self.orientacion, 0]
                # else:
                #     self.prev_x = self.pos.x
                #     return [self.orientacion, 1]
        else:
            if self.intentar_salto and self.en_suelo:
                self.intentar_salto = False
                # self.velocidad_x = 1  # Ajusta velocidad tras saltar
            return [self.orientacion, 0]

        # return [self.orientacion, 1 if self.flag_colision_horizontal else 0]

    def actualizar_animacion(self):
        self.image.fill(self.COLOR)
        self.image.fill('black',
                        pygame.rect.Rect(self.rect.w-self.rect.w/3 if self.orientacion == 1 else 0,
                                         self.rect.h/6, self.rect.w/3+1, self.rect.h/6))


class EnemigoTirador(Tirador):
    COLOR = 'darkred'
    VELOCIDAD_SALTO = -9
    DIMENSION = (32, 50)

    def __init__(self, pos: pygame.Vector2, nivel: Nivel, orientacion=-1):
        super().__init__(pos, self.DIMENSION, self.COLOR, orientacion, nivel, 1)
        self.prev_x = self.pos.x
        self.intentar_salto = False

        self.disparos_efectuados = 0
        self.rafaga = 3
        self.cooldown_rafaga = 60 * 5
        self.cooldown_disparo = self.cooldown_disparo * 1.2
        self.timer_rafaga = np.random.randint(self.cooldown_rafaga//2, self.cooldown_rafaga)

    def actualizar_timers(self):
        super().actualizar_timers()
        if self.timer_rafaga > 0:
            self.timer_rafaga -= 1

    def determinar_accion(self):
        if self.flag_colision_horizontal and self.en_suelo:
            if not self.intentar_salto or self.prev_x != self.pos.x:
                self.intentar_salto = True
                self.prev_x = self.pos.x
                # self.velocidad_x = 4  # Ajusta velocidad para saltar
                accion = [self.orientacion, 1, 0]
            else:
                # if self.prev_x == self.pos.x:
                accion = [-self.orientacion, 0, 0]
                # else:
                #     self.prev_x = self.pos.x
                #     return [self.orientacion, 1]
        else:
            if self.intentar_salto and self.en_suelo:
                self.intentar_salto = False
                # self.velocidad_x = 1  # Ajusta velocidad tras saltar
            accion = [self.orientacion, 0, 0]

        if self.disparos_efectuados < self.rafaga:
            if self.timer_rafaga == 0 and self.timer_disparo == 0:
                accion[2] = 1
                self.disparos_efectuados += 1
        else:
            self.timer_rafaga = self.cooldown_rafaga
            self.disparos_efectuados = 0

        return accion

    def actualizar_animacion(self):
        self.image.fill(self.COLOR)
        self.image.fill('black',
                        pygame.rect.Rect(self.rect.w-self.rect.w/3 if self.orientacion == 1 else 0,
                                         self.rect.h/6, self.rect.w/3+1, self.rect.h/6))


class Disparo(Entidad):
    DIMENSION_HOR = (16, 8)
    DIMENSION_VER = (8, 16)
    COLOR = 'white'
    VELOCIDAD_X = 16
    VELOCIDAD_Y = 8
    ACCION_IZQ = [-1, 0]
    ACCION_DER = [1, 0]
    ACCION_ABAJO = [0, 0]

    ORIENTACION_IZQ = -1
    ORIENTACION_ABAJO = 0
    ORIENTACION_DER = 1

    def __init__(self, rect: Union[Rect, RectType], vel: pygame.Vector2, orientacion: int, grupo: pygame.sprite.AbstractGroup, nivel: Nivel):
        self.bala_vertical = orientacion == self.ORIENTACION_ABAJO
        super().__init__(pygame.Vector2(rect.center),
                         self.DIMENSION_HOR if not self.bala_vertical else self.DIMENSION_VER,
                         self.COLOR,
                         orientacion,
                         nivel,
                         self.VELOCIDAD_X if not self.bala_vertical else 0,
                         self.ACCION_IZQ if orientacion == self.ORIENTACION_IZQ else
                         self.ACCION_DER if orientacion == self.ORIENTACION_DER else self.ACCION_ABAJO)

        copia_rect, self.rect.bottom = self.rect.copy(), rect.centery  # pos.y
        self.pos.y = self.rect.centery

        if self.orientacion == self.ORIENTACION_DER:
            self.rect.left = rect.right
            self.pos.x = rect.right
            self.rect.centery += 4
        elif self.orientacion == self.ORIENTACION_IZQ:
            self.rect.right = rect.left
            self.pos.x = self.rect.left
            self.rect.centery += 4
        else:
            self.rect.centerx = rect.centerx
            self.pos.x -= self.DIMENSION_VER[0]/2

            self.rect.top = rect.bottom
            self.pos.y = self.rect.y

            self.velocidad.y = self.VELOCIDAD_Y + max(0.0, vel.y)

        self.comprobar_colisiones_verticales = self.bala_vertical
        self.comprobar_colisiones_horizontales = not self.bala_vertical
        self.afectado_por_gravedad = self.bala_vertical
        self.grupo = grupo
        self.distancia_recorrida = 0.0

    def update(self, accion=None):
        # print(self.pos, self.rect, self.rect.left, self.rect.right, self.rect.centerx, self.rect.x)
        # print(self.pos, self.rect, self.rect.top, self.rect.bottom, self.rect.centery, self.rect.y)
        pos_ant = self.pos.x if not self.bala_vertical else self.pos.y
        super().update()
        self.distancia_recorrida += abs(self.pos.x - pos_ant) if not self.bala_vertical else abs(self.pos.y - pos_ant)

        if self.distancia_recorrida > 64 * 20:
            self.kill()

    def calcular_colisiones_horizontales(self, objs_colision=None):
        super().calcular_colisiones_horizontales()
        if self.grupo != self.nivel.jugador and (jugador := pygame.sprite.spritecollideany(self, self.nivel.jugador)):
            self.flag_colision_horizontal = True
            self.en_colision_horizontal(jugador, self.velocidad.x)
        elif self.grupo != self.nivel.enemigos and (enemigo := pygame.sprite.spritecollideany(self, self.nivel.enemigos)):
            j: Jugador = self.grupo.sprites()[0]
            j.asesinatos_tiro_horizontal_frame += 1
            self.flag_colision_horizontal = True
            self.en_colision_horizontal(enemigo, self.velocidad.x)

    def calcular_colisiones_verticales(self, objs_colision=None):
        super().calcular_colisiones_verticales()
        if self.grupo != self.nivel.jugador and (jugador := pygame.sprite.spritecollideany(self, self.nivel.jugador)):
            self.flag_colision_horizontal = True
            self.en_colision_vertical(jugador, self.velocidad.y)
        elif self.grupo != self.nivel.enemigos and (enemigo := pygame.sprite.spritecollideany(self, self.nivel.enemigos)):
            j: Jugador = self.grupo.sprites()[0]
            j.asesinatos_tiro_vertical_frame += 1
            self.flag_colision_horizontal = True
            self.en_colision_vertical(enemigo, self.velocidad.y)

    def en_colision_horizontal(self, obj, vx):
        super().en_colision_horizontal(obj, vx)
        if isinstance(obj, Entidad):
            obj.asesinado = True
            obj.kill()

    def en_colision_vertical(self, obj, vy):
        super().en_colision_vertical(obj, vy)
        if isinstance(obj, Entidad):
            obj.asesinado = True
            obj.kill()

    def resolver_flags_y_timers(self):
        super().resolver_flags_y_timers()
        if self.flag_colision_horizontal or self.flag_colision_vertical:
            self.kill()


class Rayo:
    COLOR = {
        0: (255, 255, 255),  # vacío
        1: 'darkgreen',  # bloque
        2: 'red',  # pinchos
        3: 'darkred',  # saltarín
        4: (153, 35, 35),  # tirador
        5: 'yellow',  # moneda
        6: 'violet',  # disparo jugador
        7: 'blue',  # disparo enemigo
        8: 'black'  # fondo
    }

    OBJETOS_INTERP = dict(zip(list(COLOR.keys()), np.interp(list(COLOR.keys()), [0, 8], [-1.0, 1.0])))

    def __init__(self, entidad: Entidad, ang, longitud_maxima=64*14):  # 25+64*14
        self.entidad = entidad
        self.x1 = entidad.pos.x
        self.y1 = entidad.pos.y
        self.ang = ang
        self.x2 = entidad.pos.x
        self.y2 = entidad.pos.y
        self.longitud_maxima = longitud_maxima
        self.longitud = longitud_maxima
        self.longitud_interp = 1.0
        self.flag_interseccion = False
        self.objeto_impactado = 0
        self.objeto_impactado_interp = 0.0
        self.rayo_bajo = self.ang < np.pi

    def reset(self):
        self.x1 = self.entidad.pos.x
        self.y1 = self.entidad.pos.y
        self.x2 = self.entidad.pos.x
        self.y2 = self.entidad.pos.y
        self.longitud = self.longitud_maxima
        self.longitud_interp = 1.0
        self.flag_interseccion = False
        self.objeto_impactado = 0
        self.objeto_impactado_interp = 0.0
        self.actualizar()

    def actualizar(self):
        def interseccion(x1, y1, x2, y2, x3, y3, x4, y4):
            denominador = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
            if denominador:
                t = ((x1 - x3) * (y3 - y4) - (y1 - y3) * (x3 - x4)) / denominador
                u = -((x1 - x2) * (y1 - y3) - (y1 - y2) * (x1 - x3)) / denominador
                if 0 < t < 1 and 0 < u < 1:  # u>0 o 0 < u < 1
                    return (x1 + t * (x2 - x1), y1 + t * (y2 - y1)), t
            return None

        # Actualizamos poisición en función de la del entidad
        self.x1 = self.entidad.rect.centerx
        self.y1 = self.entidad.rect.centery

        # Actualizamos ángulo en función del ángulo del entidad
        # self.ang = self.ang_offset + self.entidad.ang

        # Actualizamos puntos de destino
        self.x2 = self.x1 + np.cos(self.ang) * self.longitud_maxima
        self.y2 = self.y1 + np.sin(self.ang) * self.longitud_maxima

        # Comprobamos colisiones con entorno para ajustar el rayo
        pts_corte = None
        dist_min = 1
        objeto = None
        for bloque in (*self.entidad.nivel.pinchos, *self.entidad.nivel.bloques, *self.entidad.nivel.enemigos,
                       *self.entidad.nivel.monedas, *self.entidad.nivel.disparos):
            # if isinstance(bloque, Disparo) and bloque.grupo == bloque.nivel.jugador:
            #     continue

            b = bloque.rect
            dist_min_borde = 1
            res_bloque = None
            for borde in ((b.left, b.top, b.right, b.top), (b.right, b.top, b.right, b.bottom),
                          (b.left, b.bottom, b.right, b.bottom), (b.left, b.top, b.left, b.bottom)):
                res_borde = interseccion(self.x1, self.y1, self.x2, self.y2, *borde)
                if res_borde:
                    _, dist_borde = res_borde
                    if dist_borde < dist_min_borde:
                        res_bloque = res_borde
                        dist_min_borde = dist_borde

            # Si se devuelve una intersección con algún borde, entonces comprobamos si es mínimo
            if res_bloque:
                pts_borde, dist_borde = res_bloque
                if dist_borde < dist_min:
                    dist_min = dist_borde
                    pts_corte = pts_borde
                    objeto = bloque

        # Si existe un punto de corte (ya calculado como el mínimo), entonces lo establecemos como (x2, y2)
        if pts_corte:
            self.x2, self.y2 = pts_corte
            self.longitud = dist_min * self.longitud_maxima
            self.longitud_interp = np.interp(self.longitud, [0, self.longitud_maxima], [-1.0, 1.0])
            self.flag_interseccion = True
            self.objeto_impactado = 2 if isinstance(objeto, Pinchos) else 1 if isinstance(objeto, Bloque) else \
                5 if isinstance(objeto, Moneda) else \
                7 if isinstance(objeto, Disparo) and objeto.grupo != objeto.nivel.jugador else \
                6 if isinstance(objeto, Disparo) else 3 if isinstance(objeto, EnemigoSaltarin) else 4
        else:
            self.longitud = self.longitud_maxima
            self.longitud_interp = 1.0
            self.flag_interseccion = False
            self.objeto_impactado = 0 if not self.rayo_bajo else 8

        self.objeto_impactado_interp = self.OBJETOS_INTERP[self.objeto_impactado]

    def render(self, ventana, offset):
        """
        Renderiza el rayo.
        :param ventana: display o ventana donde se mostrará el rayo
        """
        pygame.draw.aaline(ventana, self.COLOR[self.objeto_impactado],
                           (self.x1-offset.x, self.y1-offset.y),
                           (self.x2-offset.x, self.y2-offset.y))


class SpatialHash(pygame.sprite.AbstractGroup):
    def draw(self, surface, offset=pygame.Vector2()):
        """draw all sprites onto the surface

        Group.draw(surface): return Rect_list

        Draws all of the member sprites onto the given surface.

        """
        sprites = self.sprites()
        if hasattr(surface, "blits"):
            self.spritedict.update(
                zip(sprites, surface.blits((spr.image,
                                            (spr.rect.x - offset.x, spr.rect.y - offset.y)) for spr in sprites))
            )
        else:
            for spr in sprites:
                self.spritedict[spr] = surface.blit(spr.image, spr.rect)
        self.lostsprites = []
        dirty = self.lostsprites

        return dirty


class SpatialHashSingle(pygame.sprite.GroupSingle):
    @property
    def sprite(self) -> Union[Sprite, Jugador]:
        """
        Property for the single sprite contained in this group

        :return: The sprite.
        """
        return super().sprite

    def draw(self, surface, offset=pygame.Vector2()):
        """draw all sprites onto the surface

        Group.draw(surface): return Rect_list

        Draws all of the member sprites onto the given surface.

        """
        sprites = self.sprites()
        if hasattr(surface, "blits"):
            self.spritedict.update(
                zip(sprites, surface.blits((spr.image,
                                            (spr.rect.x - offset.x, spr.rect.y - offset.y)) for spr in sprites))
            )
        else:
            # print("Estoy pintando en un lugar inesperado!")
            for spr in sprites:
                self.spritedict[spr] = surface.blit(spr.image, spr.rect)
        self.lostsprites = []
        dirty = self.lostsprites

        return dirty
