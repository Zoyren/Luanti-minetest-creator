from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BlockTypeDefinition:
    """Définition d'un bloc visuel Blockly avec sa catégorie, sa couleur et ses paramètres."""

    block_type: str
    category: str
    label: str
    color_hex: str
    is_event_root: bool = False
    default_params: Dict[str, Any] = field(default_factory=dict)
    accepts_children: bool = False


BLOCK_CATALOG: Dict[str, BlockTypeDefinition] = {
    # === 1. ÉVÉNEMENTS (Communs & Spécialisés) ===
    "event_on_start": BlockTypeDefinition(
        "event_on_start", "Événements", "Au démarrage du mod / entité", "#F59E0B", True, {}, True
    ),
    "event_mob_rightclick": BlockTypeDefinition(
        "event_mob_rightclick", "Événements", "Lorsque le joueur fait un clic droit sur le mob", "#F59E0B", True, {}, True
    ),
    "event_mob_on_step": BlockTypeDefinition(
        "event_mob_on_step", "Événements", "À chaque cycle de mise à jour du mob (on_step)", "#F59E0B", True, {}, True
    ),
    "event_block_timer": BlockTypeDefinition(
        "event_block_timer", "Événements", "Lorsqu'un timer de bloc se déclenche (toutes les N sec)", "#F59E0B", True, {"interval_sec": 5}, True
    ),
    "event_block_construct": BlockTypeDefinition(
        "event_block_construct", "Événements", "À la construction du bloc (on_construct)", "#F59E0B", True, {}, True
    ),
    "event_item_on_use": BlockTypeDefinition(
        "event_item_on_use", "Événements", "Lorsque le joueur utilise l'objet (on_use)", "#F59E0B", True, {}, True
    ),
    "event_command_execute": BlockTypeDefinition(
        "event_command_execute", "Événements", "Lorsque la commande serveur est exécutée", "#F59E0B", True, {"required_priv": "server"}, True
    ),

    # === 2. CONDITIONS ===
    "cond_if_player_wields": BlockTypeDefinition(
        "cond_if_player_wields", "Conditions", "Si le joueur tient l'objet", "#10B981", False, {"item_id": "default:apple"}, True
    ),
    "cond_if_mob_tamed": BlockTypeDefinition(
        "cond_if_mob_tamed", "Conditions", "Si le mob est apprivoisé (self.tamed == true)", "#10B981", False, {}, True
    ),
    "cond_if_node_above_group": BlockTypeDefinition(
        "cond_if_node_above_group", "Conditions", "Si le bloc au-dessus appartient au groupe", "#10B981", False, {"group_name": "vegetable"}, True
    ),
    "cond_if_player_has_priv": BlockTypeDefinition(
        "cond_if_player_has_priv", "Conditions", "Si le joueur possède le privilège", "#10B981", False, {"priv": "bring"}, True
    ),

    # === 3. VARIABLES & MATHÉMATIQUES ===
    "var_set_local": BlockTypeDefinition(
        "var_set_local", "Variables & Maths", "Définir variable locale", "#8B5CF6", False, {"var_name": "counter", "expr": "math.random(1, 100)"}, False
    ),

    # === 4. SYSTÈME DE STATISTIQUES PERSISTANTES ===
    "stat_add_value": BlockTypeDefinition(
        "stat_add_value", "Statistiques", "Modifier statistique persistante du joueur", "#EC4899", False, {"stat_name": "xp", "delta": 25}, False
    ),
    "stat_check_min": BlockTypeDefinition(
        "stat_check_min", "Statistiques", "Si la statistique du joueur >= valeur", "#EC4899", False, {"stat_name": "level", "min_val": 5}, True
    ),

    # === 5. SYSTÈME D'ÉCONOMIE (Transactions atomiques) ===
    "eco_buy_item": BlockTypeDefinition(
        "eco_buy_item", "Économie", "Transaction d'achat sécurisée (Argent -> Objet)", "#14B8A6", False, {"price": 50, "item_id": "default:diamond", "count": 1}, False
    ),
    "eco_add_money": BlockTypeDefinition(
        "eco_add_money", "Économie", "Ajouter de l'argent au joueur", "#14B8A6", False, {"amount": 100}, False
    ),

    # === 6. ACTIONS (Monde, Joueurs, Mobs, Blocs, Items) ===
    "action_tame_mob": BlockTypeDefinition(
        "action_tame_mob", "Actions", "Apprivoiser le mob (self.tamed = true)", "#3B82F6", False, {}, False
    ),
    "action_attach_mount": BlockTypeDefinition(
        "action_attach_mount", "Actions", "Attacher le joueur au mob et activer la monture", "#3B82F6", False, {"speed": 6.0}, False
    ),
    "action_play_animation": BlockTypeDefinition(
        "action_play_animation", "Actions", "Jouer une animation 3D sur le mob", "#3B82F6", False, {"anim_name": "walk", "frame_start": 1, "frame_end": 40, "fps": 15}, False
    ),
    "action_spawn_particles": BlockTypeDefinition(
        "action_spawn_particles", "Actions", "Faire apparaître des particules", "#3B82F6", False, {"texture": "heart.png", "amount": 12}, False
    ),
    "action_play_sound": BlockTypeDefinition(
        "action_play_sound", "Actions", "Jouer un son 3D", "#3B82F6", False, {"sound_name": "default_place_node", "gain": 1.0}, False
    ),
    "action_accelerate_plant_above": BlockTypeDefinition(
        "action_accelerate_plant_above", "Actions", "Accélérer la croissance de la plante au-dessus", "#3B82F6", False, {}, False
    ),
    "action_throw_teleport_pearl": BlockTypeDefinition(
        "action_throw_teleport_pearl", "Actions", "Lancer un projectile de téléportation (Enderpearl)", "#3B82F6", False, {"velocity": 18, "consume": True}, False
    ),
    "action_strike_thunder": BlockTypeDefinition(
        "action_strike_thunder", "Actions", "Déclencher un effet d'orage et de tonnerre", "#3B82F6", False, {}, False
    ),
    "action_open_formspec_gui": BlockTypeDefinition(
        "action_open_formspec_gui", "Quêtes & GUI", "Ouvrir une boîte de dialogue Formspec (BDD / Quête)", "#F97316", False, {"formname": "dialogue_bdd", "title": "PNJ Gardien", "text": "Bienvenue aventurier !"}, False
    ),

    # === 7. CONNEXIONS API HTTP EXTERNES ===
    "http_fetch_json": BlockTypeDefinition(
        "http_fetch_json", "API HTTP", "Requête HTTP GET/POST sécurisée (core.request_http_api)", "#6366F1", False, {"method": "GET", "url": "https://api.example.com/status"}, False
    ),
}


def get_preset_workspace(preset_name: str) -> Dict[str, Any]:
    """Fournit les espaces de travail Blockly préconfigurés pour les exemples du cahier des charges."""
    if preset_name == "pig":
        return {
            "preset": "pig",
            "events": [
                {
                    "type": "event_mob_rightclick",
                    "params": {},
                    "children": [
                        {
                            "type": "cond_if_player_wields",
                            "params": {"item_id": "default:apple"},
                            "children": [
                                {"type": "action_tame_mob", "params": {}},
                                {"type": "action_spawn_particles", "params": {"texture": "heart.png", "amount": 15}},
                                {"type": "action_play_sound", "params": {"sound_name": "default_dig_crumbly", "gain": 1.0}},
                            ],
                        },
                        {
                            "type": "cond_if_mob_tamed",
                            "params": {},
                            "children": [
                                {"type": "action_attach_mount", "params": {"speed": 6.0}},
                                {"type": "action_play_animation", "params": {"anim_name": "walk", "frame_start": 1, "frame_end": 40, "fps": 15}},
                            ],
                        },
                    ],
                }
            ],
        }
    if preset_name == "composter":
        return {
            "preset": "composter",
            "events": [
                {
                    "type": "event_block_timer",
                    "params": {"interval_sec": 5},
                    "children": [
                        {
                            "type": "cond_if_node_above_group",
                            "params": {"group_name": "vegetable"},
                            "children": [
                                {"type": "action_accelerate_plant_above", "params": {}},
                                {"type": "action_spawn_particles", "params": {"texture": "default_item_smoke.png", "amount": 10}},
                            ],
                        }
                    ],
                }
            ],
        }
    if preset_name == "enderpearl":
        return {
            "preset": "enderpearl",
            "events": [
                {
                    "type": "event_item_on_use",
                    "params": {},
                    "children": [
                        {"type": "action_throw_teleport_pearl", "params": {"velocity": 18, "consume": True}},
                        {"type": "action_play_sound", "params": {"sound_name": "default_glass_footstep", "gain": 0.9}},
                        {"type": "action_spawn_particles", "params": {"texture": "default_mese_crystal_fragment.png", "amount": 20}},
                    ],
                }
            ],
        }
    if preset_name == "thunder":
        return {
            "preset": "thunder",
            "events": [
                {
                    "type": "event_command_execute",
                    "params": {"required_priv": "server"},
                    "children": [
                        {"type": "action_strike_thunder", "params": {}},
                        {"type": "action_play_sound", "params": {"sound_name": "default_cool_lava", "gain": 1.5}},
                        {"type": "action_spawn_particles", "params": {"texture": "default_mese_crystal.png", "amount": 35}},
                    ],
                }
            ],
        }
    return {"preset": "empty", "events": []}