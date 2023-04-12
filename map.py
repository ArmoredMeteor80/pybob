from dataclasses import dataclass
import pygame
import pytmx
import pyscroll

import game
from player import Player, NPC


@dataclass
class Portal:
    """Data class contenant les caractéristiques des portails"""
    from_world: str
    origin_point: str
    target_world: str
    teleport_point: str


@dataclass
class Map:
    """Data class contenant les propriétés d'une carte"""
    name: str
    collision: list[pygame.Rect]
    sign_texts: dict
    group: pyscroll.PyscrollGroup
    tmx_data: pytmx.TiledMap
    portals: list[Portal]
    npcs: list[NPC]


class MapManager:
    """Gère la dynamique de carte"""

    def __init__(self, screen, player, current_map):
        # stockage des cartes dans un dictionnaire sous forme "castle" -> Map("castle", walls, group)
        self.maps = dict()
        self.screen = screen
        self.player = player
        self.current_map = current_map

        # Chargement des cartes
        self.register_map("clairiere_map", portals=[
            Portal(from_world="clairiere_map", origin_point="enter_castle", target_world="castle_map",
                   teleport_point="spawn_castle"),
            Portal(from_world="clairiere_map", origin_point="enter_village", target_world="village_map",
                   teleport_point="spawn_village1")])

        self.register_map("village_map", portals=[
            Portal(from_world="village_map", origin_point="enter_clairiere", target_world="clairiere_map",
                   teleport_point="spawn_clairiere2"),
            Portal(from_world="village_map", origin_point="enter_castle", target_world="castle_map",
                   teleport_point="spawn_castle"),
            Portal(from_world="village_map", origin_point="enter_test", target_world="test_map",
                   teleport_point="spawn_test")])

        self.register_map("castle_map", portals=[
            Portal(from_world="castle_map", origin_point="enter_clairiere", target_world="clairiere_map",
                   teleport_point="spawn_clairiere1")
        ], npcs=[NPC('lutin', nb_points=6, dialog=["Bonne aventure", "je m'appelle Paul", "A+"])])

        self.register_map("test_map", portals=[
            Portal(from_world="test_map", origin_point="enter_clairiere", target_world="clairiere_map",
                   teleport_point="spawn_clairiere2")])

        self.teleport_npcs()

    def check_dialog_collisions(self, dialog_box):
        """Détecte les collisions avec les PNJ et les Panneaux"""
        for sprite in self.get_group().sprites():
            # Dialogues avec PNJ
            if sprite.rect.colliderect(self.player.rect) and type(sprite) is NPC:
                dialog_box.execute(sprite.dialog)
            # Dialogues avec Panneaux
            try:
                for k in self.get_sign_collision().keys():
                    if sprite.rect.colliderect(self.get_sign_collision()[k][0]):
                        dialog_box.execute(self.get_sign_collision()[k][1])
            except:
                None

    def terminate_dialog(self, dialog_box):
        """Met fin au dialogue"""
        player_position = self.player.old_position
        if player_position != self.player.position:
            dialog_box.terminate()

    def check_collisions(self):
        """Détecte les collisions"""
        # Support des portails
        for portal in self.get_map().portals:
            if portal.from_world == self.current_map:
                point = self.get_object(portal.origin_point)
                rect = pygame.Rect(point.x, point.y, point.width, point.height)

                if self.player.feet.colliderect(rect):
                    copy_portal = portal
                    self.current_map = portal.target_world
                    self.teleport_player(copy_portal.teleport_point)
                    self.fade_in((49, 26, 18), 5)
                    self.fade_out((49, 26, 18), 5)

        # Support des collisions
        for sprite in self.get_group().sprites():

            if type(sprite) is NPC:
                if sprite.rect.colliderect(self.player.feet):
                    sprite.speed = 0
                    self.player.move_back()
                else:
                    sprite.speed = 1
            if sprite.feet.collidelist(self.get_collision()) > -1:
                sprite.move_back()

    def fade_in(self, color, speed):
        """Filtre de fondu"""
        # on fait une copie de l'écran
        screen_image = self.screen.copy()
        # Surface qui va faire le fondu en augmentant et baissant sa valeur d'alpha
        fade = pygame.Surface(self.screen.get_size()).convert_alpha()
        fade.fill(color)
        for alpha in range(0, 256, speed):
            self.screen.blit(screen_image, (0, 0))
            fade.set_alpha(alpha)
            self.screen.blit(fade, (0, 0))
            pygame.display.update()

    def fade_out(self, color, speed):
        """Filtre de fondu inverse"""
        fade = pygame.Surface(self.screen.get_size()).convert_alpha()
        fade.fill(color)
        # Fondu inverse, on met d'abord à jour le joueur qui se met sur la nouvelle carte chargée,
        # puis on draw deux fois de sorte à afficher la carte derrière le fondu et centrer la caméra sur le joueur
        self.player.update()
        self.draw()
        self.draw()
        # Enfin on fait une copie de ce qu'il y a derriere le fondu (on exclut le fondu de la copie)
        fade_rect = fade.get_rect()
        self.screen.set_clip(fade_rect)
        screen_image = self.screen.copy()
        self.screen.set_clip(None)
        for alpha in range(255, -1, -speed):
            self.screen.blit(screen_image, (0, 0))
            fade.set_alpha(alpha)
            self.screen.blit(fade, (0, 0))
            pygame.display.update()

    def teleport_player(self, name):
        """Téléporte le joueur au point donné en paramètre"""
        point = self.get_object(name)
        self.player.position[0] = point.x
        self.player.position[1] = point.y
        self.player.save_location()

    def register_map(self, name, portals=[], npcs=[]):
        """Charge les différentes cartes"""
        # Charge la carte tmx en créant un objet "TiledMap" contenant les calques, objets et images d'une carte .tmx
        tmx_data = pytmx.util_pygame.load_pygame(f"assets/maps/{name}.tmx")
        # On récupère les données du fichier .tmx dans map_data
        map_data = pyscroll.data.TiledMapData(tmx_data)
        # On charge les calques du fichier .tmx
        map_layer = pyscroll.orthographic.BufferedRenderer(map_data, self.screen.get_size(), alpha=True)
        map_layer.zoom = 4

        # Définition d'une liste stockant les boites de collision
        collision = []
        # Définition d'un dictionnaire stockant les textes des panneaux
        sign_texts = {}
        # On récupère tous les objets de la carte
        for obj in tmx_data.objects:
            if obj.name == "collision":
                collision.append(pygame.Rect(obj.x, obj.y, obj.width, obj.height))
            if "sign" in obj.name:
                sign_texts[obj.name] = (pygame.Rect(obj.x, obj.y, obj.width, obj.height), [])
                for prop in obj.properties:
                    if prop.startswith("text"):
                        sign_texts[obj.name][1].append(obj.properties[prop])

        # Dessiner le groupe de calques en créant un objet "PyscrollGroup"
        group = pyscroll.PyscrollGroup(map_layer=map_layer, default_layer=4)
        group.add(self.player)

        # On récupère tous les PNJ pour les ajouter au groupe
        for npc in npcs:
            group.add(npc)

        # Création d'un objet Map qu'on injecte dans le dictionnaire les repertoriant
        self.maps[name] = Map(name, collision, sign_texts, group, tmx_data, portals, npcs)

    # Accesseurs (getters)
    def get_map(self):
        """Renvoie la carte actuellement affichée"""
        return self.maps[self.current_map]

    def get_group(self):
        """Renvoie le groupe"""
        return self.get_map().group

    def get_collision(self):
        """Renvoie les collisions"""
        return self.get_map().collision

    def get_sign_collision(self):
        """Renvoie les collisions avec les panneaux"""
        return self.get_map().sign_texts

    def get_object(self, name):
        """Renvoie l'objet demandé"""
        return self.get_map().tmx_data.get_object_by_name(name)

    def teleport_npcs(self):
        """Teleporte les PNJ"""
        for map in self.maps:
            map_data = self.maps[map]
            npcs = map_data.npcs

            for npc in npcs:
                npc.load_points(map_data.tmx_data)
                npc.teleport_spawn()

    def draw(self):
        """Dessine la carte"""
        self.get_group().draw(self.screen)
        self.get_group().center(self.player.rect.center)

    def update(self):
        """Actualise le groupe"""
        self.get_group().update()
        self.check_collisions()

        for npc in self.get_map().npcs:
            npc.move()
