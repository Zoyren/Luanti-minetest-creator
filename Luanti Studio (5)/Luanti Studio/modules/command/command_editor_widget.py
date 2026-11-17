# -*- coding: utf-8 -*-
"""
modules/command/command_editor_widget.py
Workbench 1 (Catégorie Commands) — Système de Commandes Serveur Luanti 100% Customisable (Tâche 5) :
- Constructeur d'Arguments Typés (<joueur>, <item>, <entier>, <x y z>, <choix>, <texte>) avec parseur Lua automatique
- Gestionnaire de Sous-Commandes imbriquées (ex: /boutique ouvrir, /boutique bonus, /boutique gardien)
- Actions Multiples combinables (Ouvrir GUI, Donner Item, Invoquer Mob 3D, Téléporter, Son, Métadonnées Joueur)
- Simulateur de Terminal In-Game interactif testant les arguments et sous-commandes en direct.
"""

from dataclasses import dataclass, asdict
from typing import Any, Dict, List

try:
    from PyQt6.QtCore import Qt, pyqtSignal
    from PyQt6.QtGui import QFont
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox,
        QSpinBox, QGroupBox, QFormLayout, QPlainTextEdit,
        QListWidget, QListWidgetItem, QTabWidget, QScrollArea
    )
except ImportError:
    from PyQt5.QtCore import Qt, pyqtSignal
    from PyQt5.QtGui import QFont
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QLabel, QLineEdit, QPushButton, QCheckBox, QComboBox,
        QSpinBox, QGroupBox, QFormLayout, QPlainTextEdit,
        QListWidget, QListWidgetItem, QTabWidget, QScrollArea
    )


ARG_TYPES = [
    ("string", "🔤 Mot / Identifiant (string)"),
    ("player", "👤 Joueur connecté (player)"),
    ("int", "🔢 Nombre entier (int)"),
    ("item", "⚔️ ID d'Item / Bloc (item)"),
    ("pos", "📍 Coordonnées X,Y,Z (pos)"),
    ("text", "📝 Texte libre (greedy text)"),
]

SUBCOMMAND_ACTION_TYPES = [
    ("open_gui", "🖼️ Ouvrir une GUI Formspec"),
    ("give_item", "🎁 Donner un Item au joueur"),
    ("spawn_mob", "🐺 Faire apparaître un Mob 3D"),
    ("teleport", "⚡ Téléporter le joueur (X,Y,Z)"),
    ("heal", "❤️ Modifier les PV du joueur"),
    ("set_meta", "💾 Sauvegarder une Stat/Meta joueur"),
    ("play_sound", "🔊 Jouer un effet sonore"),
    ("broadcast", "📢 Annonce globale sur le serveur"),
]


@dataclass
class CommandArgumentDef:
    name: str = "cible"
    arg_type: str = "string"
    required: bool = True
    default_val: str = ""

    def format_syntax(self) -> str:
        if self.required:
            return f"<{self.name}:{self.arg_type}>"
        default_sfx = f"={self.default_val}" if self.default_val else ""
        return f"[{self.name}:{self.arg_type}{default_sfx}]"


@dataclass
class SubCommandDef:
    sub_name: str = "aide"
    description: str = "Affiche l'aide de la sous-commande"
    action_type: str = "open_gui"
    action_value: str = "mon_mod:boutique_gui"
    feedback_msg: str = "Sous-commande exécutée !"


class CommandEditorWidget(QWidget):
    """
    Éditeur Pro de Commandes Chat Luanti (/commande) avec Arguments Typés,
    Sous-commandes, Actions Chaînées et Simulateur de Terminal In-Game.
    """
    commandUpdated = pyqtSignal(str)
    openGuiBuilderRequested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.linked_formspec_name = "mon_mod:boutique_gui"
        self.arguments: List[CommandArgumentDef] = [
            CommandArgumentDef("onglet", "string", False, "accueil"),
            CommandArgumentDef("quantite", "int", False, "1"),
        ]
        self.subcommands: List[SubCommandDef] = [
            SubCommandDef("ouvrir", "Ouvre l'interface graphique principale", "open_gui", "mon_mod:boutique_gui", "Ouverture de la GUI..."),
            SubCommandDef("bonus", "Donne un cristal bonus au joueur", "give_item", "default:mese_crystal 2", "🎁 Vous recevez 2 Cristaux de Mese !"),
            SubCommandDef("gardien", "Invoque le Renard Chibi Bleu près de vous", "spawn_mob", "mon_mod:renard_bleu", "🐺 Un Renard Chibi Bleu apparaît !"),
        ]
        self._updating_ui = False
        self._build_ui()
        self._refresh_args_list()
        self._refresh_subcommands_list()
        self._refresh_lua_preview()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.inp_name.text(),
            "params": self.inp_params.text(),
            "desc": self.inp_desc.text(),
            "priv_interact": self.chk_priv_interact.isChecked(),
            "priv_shout": self.chk_priv_shout.isChecked(),
            "priv_server": self.chk_priv_server.isChecked(),
            "priv_teleport": self.chk_priv_teleport.isChecked(),
            "priv_bring": self.chk_priv_bring.isChecked(),
            "custom_priv": self.inp_custom_priv.text(),
            "action_idx": self.combo_action.currentIndex(),
            "feedback": self.inp_chat_feedback.text(),
            "reward": self.inp_reward_item.text(),
            "sound_fx": self.inp_sound_fx.text(),
            "cooldown": self.spn_cooldown.value(),
            "arguments": [asdict(a) for a in self.arguments],
            "subcommands": [asdict(s) for s in self.subcommands],
        }

    def load_from_dict(self, cdata: Dict[str, Any], default_cmd_name: str = "boutique"):
        self._updating_ui = True
        self.inp_name.setText(cdata.get("name", default_cmd_name))
        self.inp_params.setText(cdata.get("params", "[ouvrir|bonus|gardien] [onglet:string=accueil]"))
        self.inp_desc.setText(cdata.get("desc", f"Commande /{default_cmd_name}"))
        self.chk_priv_interact.setChecked(bool(cdata.get("priv_interact", True)))
        self.chk_priv_shout.setChecked(bool(cdata.get("priv_shout", False)))
        self.chk_priv_server.setChecked(bool(cdata.get("priv_server", False)))
        self.chk_priv_teleport.setChecked(bool(cdata.get("priv_teleport", False)))
        self.chk_priv_bring.setChecked(bool(cdata.get("priv_bring", False)))
        self.inp_custom_priv.setText(cdata.get("custom_priv", ""))
        self.combo_action.setCurrentIndex(int(cdata.get("action_idx", 0)))
        self.inp_chat_feedback.setText(cdata.get("feedback", "Commande exécutée."))
        self.inp_reward_item.setText(cdata.get("reward", "default:diamond 5"))
        self.inp_sound_fx.setText(cdata.get("sound_fx", ""))
        self.spn_cooldown.setValue(int(cdata.get("cooldown", 0)))

        if "arguments" in cdata and isinstance(cdata["arguments"], list):
            self.arguments = [CommandArgumentDef(**a) for a in cdata["arguments"]]
        if "subcommands" in cdata and isinstance(cdata["subcommands"], list):
            self.subcommands = [SubCommandDef(**s) for s in cdata["subcommands"]]

        self._updating_ui = False
        self._refresh_args_list()
        self._refresh_subcommands_list()
        self._refresh_lua_preview()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # =====================================================================
        # PANNEAU GAUCHE : ONGLETS DE CONFIGURATION (1. Général | 2. Arguments & Sous-commandes)
        # =====================================================================
        left_tabs = QTabWidget()
        left_tabs.setMinimumWidth(420)

        # --- ONGLET 1 : IDENTITÉ, PRIVILÈGES & ACTION PRINCIPALE ---
        tab1_scroll = QScrollArea()
        tab1_scroll.setWidgetResizable(True)
        tab1_scroll.setFrameShape(QFrame.Shape.NoFrame)

        tab1 = QFrame()
        t1_layout = QVBoxLayout(tab1)
        t1_layout.setContentsMargins(10, 10, 10, 10)
        t1_layout.setSpacing(10)

        banner = QLabel("⌨️ 1. IDENTITÉ, PRIVILÈGES & ACTION PAR DÉFAUT")
        banner.setStyleSheet(
            "font-size: 13px; font-weight: 800; color: #60a5fa; "
            "padding: 7px 10px; background-color: #12151e; border-radius: 6px; border: 1px solid #2563eb;"
        )
        t1_layout.addWidget(banner)

        grp_ident = QGroupBox("Identité & Syntaxe (/help)")
        form_ident = QFormLayout(grp_ident)
        form_ident.setSpacing(8)

        self.inp_name = QLineEdit("boutique")
        self.inp_name.setStyleSheet("font-size: 14px; font-weight: bold; color: #38bdf8;")
        self.inp_name.textChanged.connect(self._refresh_lua_preview)

        self.inp_params = QLineEdit("[ouvrir|bonus|gardien] [onglet:string=accueil] [quantite:int=1]")
        self.inp_params.textChanged.connect(self._refresh_lua_preview)

        btn_sync_syntax = QPushButton("🔄 Générer la syntaxe depuis les Arguments/Sous-commandes")
        btn_sync_syntax.clicked.connect(self._sync_params_syntax_string)

        self.inp_desc = QLineEdit("Ouvre la boutique royale ou exécute une sous-commande rapide")
        self.inp_desc.textChanged.connect(self._refresh_lua_preview)

        form_ident.addRow("Commande (sans /) :", self.inp_name)
        form_ident.addRow("Syntaxe (/help) :", self.inp_params)
        form_ident.addRow("", btn_sync_syntax)
        form_ident.addRow("Description :", self.inp_desc)
        t1_layout.addWidget(grp_ident)

        grp_privs = QGroupBox("Privilèges Requis & Sécurité")
        priv_layout = QVBoxLayout(grp_privs)

        priv_grid = QHBoxLayout()
        self.chk_priv_interact = QCheckBox("interact")
        self.chk_priv_interact.setChecked(True)
        self.chk_priv_shout = QCheckBox("shout")
        self.chk_priv_server = QCheckBox("server (Admin)")
        self.chk_priv_teleport = QCheckBox("teleport")
        self.chk_priv_bring = QCheckBox("bring")

        for chk in (
            self.chk_priv_interact, self.chk_priv_shout,
            self.chk_priv_server, self.chk_priv_teleport, self.chk_priv_bring
        ):
            chk.toggled.connect(self._refresh_lua_preview)
            priv_grid.addWidget(chk)
        priv_layout.addLayout(priv_grid)

        custom_priv_row = QHBoxLayout()
        custom_priv_row.addWidget(QLabel("Privilège custom :"))
        self.inp_custom_priv = QLineEdit("")
        self.inp_custom_priv.setPlaceholderText("ex: vip, moderateur, chef_guilde")
        self.inp_custom_priv.textChanged.connect(self._refresh_lua_preview)
        custom_priv_row.addWidget(self.inp_custom_priv, 1)
        priv_layout.addLayout(custom_priv_row)

        t1_layout.addWidget(grp_privs)

        grp_action = QGroupBox("Action Principale (Quand tapée sans sous-commande)")
        act_form = QFormLayout(grp_action)
        act_form.setSpacing(8)

        self.combo_action = QComboBox()
        self.combo_action.addItems([
            "🖼️ Ouvrir la GUI Personnalisée (Atelier 2) + Logique",
            "🧩 Exécuter uniquement les Sous-Commandes / Blockly",
            "🎁 Donner un Item / Récompense au joueur",
            "⚡ Téléporter le joueur aux coordonnées cibles",
            "🐺 Faire apparaître un Mob 3D du Mod devant le joueur",
            "❤️ Soigner / Restaurer les PV du joueur",
        ])
        self.combo_action.currentIndexChanged.connect(self._refresh_lua_preview)
        act_form.addRow("Action :", self.combo_action)

        self.inp_chat_feedback = QLineEdit("Bienvenue dans la boutique ! Utilisez les onglets ou boutons.")
        self.inp_chat_feedback.textChanged.connect(self._refresh_lua_preview)
        act_form.addRow("Message Chat :", self.inp_chat_feedback)

        self.inp_reward_item = QLineEdit("default:diamond 5")
        self.inp_reward_item.textChanged.connect(self._refresh_lua_preview)
        act_form.addRow("Cible (Item/Pos/Mob) :", self.inp_reward_item)

        self.inp_sound_fx = QLineEdit("")
        self.inp_sound_fx.setPlaceholderText("Optionnel : ex. default_place_node")
        self.inp_sound_fx.textChanged.connect(self._refresh_lua_preview)
        act_form.addRow("Effet Sonore :", self.inp_sound_fx)

        self.spn_cooldown = QSpinBox()
        self.spn_cooldown.setRange(0, 3600)
        self.spn_cooldown.setValue(0)
        self.spn_cooldown.setSuffix(" sec")
        self.spn_cooldown.valueChanged.connect(self._refresh_lua_preview)
        act_form.addRow("Cooldown :", self.spn_cooldown)

        btn_go_gui = QPushButton("🖼️ Ouvrir l'Éditeur de GUI Personnalisée (Atelier 2)")
        btn_go_gui.setObjectName("PrimaryButton")
        btn_go_gui.clicked.connect(self.openGuiBuilderRequested.emit)
        act_form.addRow("", btn_go_gui)

        t1_layout.addWidget(grp_action)
        t1_layout.addStretch()
        tab1_scroll.setWidget(tab1)
        left_tabs.addTab(tab1_scroll, "⌨️ 1. Général & Action")

        # --- ONGLET 2 : CONSTRUCTEUR D'ARGUMENTS TYPÉS & SOUS-COMMANDES ---
        tab2_scroll = QScrollArea()
        tab2_scroll.setWidgetResizable(True)
        tab2_scroll.setFrameShape(QFrame.Shape.NoFrame)

        tab2 = QFrame()
        t2_layout = QVBoxLayout(tab2)
        t2_layout.setContentsMargins(10, 10, 10, 10)
        t2_layout.setSpacing(10)

        grp_args = QGroupBox("🧩 Constructeur d'Arguments Typés (Validation Lua Automatique)")
        args_layout = QVBoxLayout(grp_args)
        args_layout.setSpacing(6)

        self.args_list = QListWidget()
        self.args_list.setMaximumHeight(110)
        self.args_list.currentRowChanged.connect(self._on_arg_row_selected)
        args_layout.addWidget(self.args_list)

        arg_form_row1 = QHBoxLayout()
        self.inp_arg_name = QLineEdit("cible")
        self.inp_arg_name.setPlaceholderText("Nom argument")
        self.combo_arg_type = QComboBox()
        for k, lbl in ARG_TYPES:
            self.combo_arg_type.addItem(lbl, k)
        self.chk_arg_req = QCheckBox("Requis")
        self.chk_arg_req.setChecked(True)
        self.inp_arg_def = QLineEdit("")
        self.inp_arg_def.setPlaceholderText("Défaut")

        arg_form_row1.addWidget(QLabel("Nom:"))
        arg_form_row1.addWidget(self.inp_arg_name, 1)
        arg_form_row1.addWidget(self.combo_arg_type, 1)
        arg_form_row1.addWidget(self.chk_arg_req)
        arg_form_row1.addWidget(self.inp_arg_def, 1)
        args_layout.addLayout(arg_form_row1)

        arg_btn_row = QHBoxLayout()
        btn_add_arg = QPushButton("➕ Ajouter Argument")
        btn_add_arg.setObjectName("PrimaryButton")
        btn_add_arg.clicked.connect(self._add_typed_arg)
        btn_upd_arg = QPushButton("✏️ Mettre à jour")
        btn_upd_arg.clicked.connect(self._update_selected_arg)
        btn_del_arg = QPushButton("🗑️ Supprimer")
        btn_del_arg.setObjectName("DangerButton")
        btn_del_arg.clicked.connect(self._delete_selected_arg)
        arg_btn_row.addWidget(btn_add_arg)
        arg_btn_row.addWidget(btn_upd_arg)
        arg_btn_row.addWidget(btn_del_arg)
        args_layout.addLayout(arg_btn_row)

        t2_layout.addWidget(grp_args)

        grp_sub = QGroupBox("🌿 Sous-Commandes Imbriquées (ex: /boutique bonus, /boutique gardien)")
        sub_layout = QVBoxLayout(grp_sub)
        sub_layout.setSpacing(6)

        self.sub_list = QListWidget()
        self.sub_list.setMaximumHeight(120)
        self.sub_list.currentRowChanged.connect(self._on_sub_row_selected)
        sub_layout.addWidget(self.sub_list)

        sub_form = QFormLayout()
        sub_form.setSpacing(6)

        self.inp_sub_name = QLineEdit("bonus")
        sub_form.addRow("Mot-clé sous-commande :", self.inp_sub_name)

        self.combo_sub_act = QComboBox()
        for k, lbl in SUBCOMMAND_ACTION_TYPES:
            self.combo_sub_act.addItem(lbl, k)
        sub_form.addRow("Action déclenchée :", self.combo_sub_act)

        self.inp_sub_val = QLineEdit("default:mese_crystal 2")
        sub_form.addRow("Paramètre (GUI/Item/Mob/Pos) :", self.inp_sub_val)

        self.inp_sub_msg = QLineEdit("🎁 Vous recevez votre récompense !")
        sub_form.addRow("Message retour :", self.inp_sub_msg)

        sub_layout.addLayout(sub_form)

        sub_btn_row = QHBoxLayout()
        btn_add_sub = QPushButton("➕ Ajouter Sous-Commande")
        btn_add_sub.setObjectName("PrimaryButton")
        btn_add_sub.clicked.connect(self._add_subcommand)
        btn_upd_sub = QPushButton("✏️ Mettre à jour")
        btn_upd_sub.clicked.connect(self._update_selected_subcommand)
        btn_del_sub = QPushButton("🗑️ Supprimer")
        btn_del_sub.setObjectName("DangerButton")
        btn_del_sub.clicked.connect(self._delete_selected_subcommand)
        sub_btn_row.addWidget(btn_add_sub)
        sub_btn_row.addWidget(btn_upd_sub)
        sub_btn_row.addWidget(btn_del_sub)
        sub_layout.addLayout(sub_btn_row)

        t2_layout.addWidget(grp_sub)
        t2_layout.addStretch()
        tab2_scroll.setWidget(tab2)
        left_tabs.addTab(tab2_scroll, "🌿 2. Arguments & Sous-Commandes")

        splitter.addWidget(left_tabs)

        # =====================================================================
        # PANNEAU DROIT : SIMULATEUR DE TERMINAL IN-GAME + CODE LUA GÉNÉRÉ
        # =====================================================================
        right_panel = QFrame()
        right_panel.setProperty("class", "InspectorPanel")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(10, 10, 10, 10)
        right_layout.setSpacing(8)

        lbl_sim = QLabel("🎮 Simulateur de Terminal Luanti (Testez vos sous-commandes & arguments)")
        lbl_sim.setStyleSheet("font-weight: bold; color: #38bdf8; font-size: 13px;")
        right_layout.addWidget(lbl_sim)

        self.chat_log = QPlainTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.setMaximumHeight(165)
        self.chat_log.setStyleSheet(
            "background-color: #0b0e14; color: #a7f3d0; font-family: Consolas, monospace; "
            "font-size: 12px; border: 1px solid #1e293b;"
        )
        self.chat_log.setPlainText(
            "[Serveur Luanti] Connecté en tant que 'Player1'\n"
            "💡 Astuce : Testez '/boutique', '/boutique bonus' ou '/boutique gardien' !"
        )
        right_layout.addWidget(self.chat_log)

        sim_input_row = QHBoxLayout()
        self.inp_test_cmd = QLineEdit("/boutique bonus")
        self.inp_test_cmd.returnPressed.connect(self._simulate_command_execution)
        btn_test = QPushButton("▶ Exécuter dans le Terminal")
        btn_test.setObjectName("PrimaryButton")
        btn_test.clicked.connect(self._simulate_command_execution)
        sim_input_row.addWidget(self.inp_test_cmd, 1)
        sim_input_row.addWidget(btn_test)
        right_layout.addLayout(sim_input_row)

        lbl_lua = QLabel("📜 Code Lua Généré (Parseur d'Arguments, Sous-Commandes & Cooldown) :")
        lbl_lua.setStyleSheet("font-weight: bold; color: #93c5fd; margin-top: 4px;")
        right_layout.addWidget(lbl_lua)

        self.lua_preview = QPlainTextEdit()
        self.lua_preview.setReadOnly(True)
        font = QFont("Consolas", 10)
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.lua_preview.setFont(font)
        right_layout.addWidget(self.lua_preview, 1)

        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([640, 620])
        root.addWidget(splitter)

    def _refresh_args_list(self):
        self.args_list.blockSignals(True)
        self.args_list.clear()
        for arg in self.arguments:
            req_tag = "Obligatoire" if arg.required else f"Optionnel (défaut='{arg.default_val}')"
            self.args_list.addItem(QListWidgetItem(f"{arg.format_syntax()}  —  {req_tag}"))
        self.args_list.blockSignals(False)

    def _on_arg_row_selected(self, row: int):
        if 0 <= row < len(self.arguments):
            a = self.arguments[row]
            self.inp_arg_name.setText(a.name)
            for i in range(self.combo_arg_type.count()):
                if self.combo_arg_type.itemData(i) == a.arg_type:
                    self.combo_arg_type.setCurrentIndex(i)
                    break
            self.chk_arg_req.setChecked(a.required)
            self.inp_arg_def.setText(a.default_val)

    def _add_typed_arg(self):
        name = self.inp_arg_name.text().strip().replace(" ", "_") or f"arg_{len(self.arguments)+1}"
        atype = self.combo_arg_type.currentData() or "string"
        req = self.chk_arg_req.isChecked()
        dval = self.inp_arg_def.text().strip()
        self.arguments.append(CommandArgumentDef(name, atype, req, dval))
        self._refresh_args_list()
        self._sync_params_syntax_string()
        self._refresh_lua_preview()

    def _update_selected_arg(self):
        row = self.args_list.currentRow()
        if 0 <= row < len(self.arguments):
            a = self.arguments[row]
            a.name = self.inp_arg_name.text().strip().replace(" ", "_") or a.name
            a.arg_type = self.combo_arg_type.currentData() or "string"
            a.required = self.chk_arg_req.isChecked()
            a.default_val = self.inp_arg_def.text().strip()
            self._refresh_args_list()
            self._sync_params_syntax_string()
            self._refresh_lua_preview()

    def _delete_selected_arg(self):
        row = self.args_list.currentRow()
        if 0 <= row < len(self.arguments):
            del self.arguments[row]
            self._refresh_args_list()
            self._sync_params_syntax_string()
            self._refresh_lua_preview()

    def _refresh_subcommands_list(self):
        self.sub_list.blockSignals(True)
        self.sub_list.clear()
        for sub in self.subcommands:
            self.sub_list.addItem(
                QListWidgetItem(f"/{self.inp_name.text().strip() or 'cmd'} {sub.sub_name}  ➔  [{sub.action_type}] {sub.action_value}")
            )
        self.sub_list.blockSignals(False)

    def _on_sub_row_selected(self, row: int):
        if 0 <= row < len(self.subcommands):
            s = self.subcommands[row]
            self.inp_sub_name.setText(s.sub_name)
            for i in range(self.combo_sub_act.count()):
                if self.combo_sub_act.itemData(i) == s.action_type:
                    self.combo_sub_act.setCurrentIndex(i)
                    break
            self.inp_sub_val.setText(s.action_value)
            self.inp_sub_msg.setText(s.feedback_msg)

    def _add_subcommand(self):
        sname = self.inp_sub_name.text().strip().lower().replace(" ", "_") or f"sub_{len(self.subcommands)+1}"
        sact = self.combo_sub_act.currentData() or "open_gui"
        sval = self.inp_sub_val.text().strip()
        smsg = self.inp_sub_msg.text().strip()
        self.subcommands.append(SubCommandDef(sname, f"Sous-commande {sname}", sact, sval, smsg))
        self._refresh_subcommands_list()
        self._sync_params_syntax_string()
        self._refresh_lua_preview()

    def _update_selected_subcommand(self):
        row = self.sub_list.currentRow()
        if 0 <= row < len(self.subcommands):
            s = self.subcommands[row]
            s.sub_name = self.inp_sub_name.text().strip().lower().replace(" ", "_") or s.sub_name
            s.action_type = self.combo_sub_act.currentData() or "open_gui"
            s.action_value = self.inp_sub_val.text().strip()
            s.feedback_msg = self.inp_sub_msg.text().strip()
            self._refresh_subcommands_list()
            self._sync_params_syntax_string()
            self._refresh_lua_preview()

    def _delete_selected_subcommand(self):
        row = self.sub_list.currentRow()
        if 0 <= row < len(self.subcommands):
            del self.subcommands[row]
            self._refresh_subcommands_list()
            self._sync_params_syntax_string()
            self._refresh_lua_preview()

    def _sync_params_syntax_string(self):
        parts = []
        if self.subcommands:
            subs = "|".join(s.sub_name for s in self.subcommands)
            parts.append(f"[{subs}]")
        for a in self.arguments:
            parts.append(a.format_syntax())
        self.inp_params.setText(" ".join(parts))

    def _collect_privs_list(self) -> List[str]:
        privs = []
        if self.chk_priv_interact.isChecked():
            privs.append("interact")
        if self.chk_priv_shout.isChecked():
            privs.append("shout")
        if self.chk_priv_server.isChecked():
            privs.append("server")
        if self.chk_priv_teleport.isChecked():
            privs.append("teleport")
        if self.chk_priv_bring.isChecked():
            privs.append("bring")
        custom = self.inp_custom_priv.text().strip()
        if custom:
            for p in custom.split(","):
                clean = p.strip()
                if clean and clean not in privs:
                    privs.append(clean)
        return privs

    @staticmethod
    def _compile_sub_action_lines(act_type: str, act_val: str, feedback: str, formspec_fallback: str, indent: str) -> List[str]:
        out = []
        safe_val = act_val.replace('"', '\\"')
        safe_msg = feedback.replace('"', '\\"')

        if act_type == "open_gui":
            gui_target = safe_val or formspec_fallback
            out.append(
                f'{indent}if custom_gui_show then custom_gui_show(player, "{gui_target}") '
                f'else minetest.show_formspec(name, "{gui_target}", custom_formspec_string or "formspec_version[6]size[11,9.5]") end'
            )
        elif act_type == "give_item":
            out.append(f'{indent}player:get_inventory():add_item("main", "{safe_val or "default:diamond 1"}")')
        elif act_type == "spawn_mob":
            out.extend([
                f"{indent}local ppos = player:get_pos()",
                f"{indent}local dir = player:get_look_dir()",
                f'{indent}minetest.add_entity({{x=ppos.x+dir.x*2, y=ppos.y+0.5, z=ppos.z+dir.z*2}}, "{safe_val or "mon_mod:renard_bleu"}")',
            ])
        elif act_type == "teleport":
            out.extend([
                f'{indent}local tpos = minetest.string_to_pos("{safe_val}") or {{x=0, y=10, z=0}}',
                f"{indent}player:set_pos(tpos)",
            ])
        elif act_type == "heal":
            hp_delta = int(safe_val) if safe_val.lstrip("-").isdigit() else 20
            out.append(f"{indent}player:set_hp(player:get_hp() + ({hp_delta}))")
        elif act_type == "set_meta":
            k, _, v = safe_val.partition("=")
            k = k.strip() or "rang"
            v = v.strip() or "VIP"
            out.append(f'{indent}player:get_meta():set_string("{k}", "{v}")')
        elif act_type == "play_sound":
            out.append(f'{indent}minetest.sound_play("{safe_val or "default_place_node"}", {{to_player = name, gain = 1.0}})')
        elif act_type == "broadcast":
            out.append(f'{indent}minetest.chat_send_all("[Annonce] " .. "{safe_msg or safe_val}")')

        if safe_msg:
            out.append(f'{indent}return true, "{safe_msg}"')
        else:
            out.append(f"{indent}return true")
        return out

    def generate_lua_code(self) -> str:
        cmd = self.inp_name.text().strip().lstrip("/") or "commande"
        params = self.inp_params.text().strip().replace('"', '\\"')
        desc = self.inp_desc.text().strip().replace('"', '\\"')
        privs = self._collect_privs_list()
        privs_lua = ", ".join(f"{p} = true" for p in privs)
        feedback = self.inp_chat_feedback.text().strip().replace('"', '\\"')
        cooldown = self.spn_cooldown.value()
        act_idx = self.combo_action.currentIndex()
        extra_val = self.inp_reward_item.text().strip().replace('"', '\\"')
        snd_fx = self.inp_sound_fx.text().strip().replace('"', '\\"')

        lines = [
            f"-- ============================================================================",
            f"-- COMMANDE SERVEUR LUANTI : /{cmd}",
            f"-- ============================================================================",
        ]
        if cooldown > 0:
            lines.append(f"local _{cmd}_cooldowns = {{}}\n")

        lines.extend([
            f'minetest.register_chatcommand("{cmd}", {{',
            f'    params = "{params}",',
            f'    description = "{desc}",',
            f'    privs = {{{privs_lua}}},',
            "    func = function(name, param)",
            "        local player = minetest.get_player_by_name(name)",
            "        if not player then",
            '            return false, "Ce joueur doit être connecté en jeu."',
            "        end",
        ])

        if cooldown > 0:
            lines.extend([
                "        local now = os.time()",
                f"        if _{cmd}_cooldowns[name] and (now - _{cmd}_cooldowns[name]) < {cooldown} then",
                f'            local wait = {cooldown} - (now - _{cmd}_cooldowns[name])',
                '            return false, "⏳ Veuillez patienter " .. wait .. "s avant de réutiliser /' + cmd + '."',
                "        end",
                f"        _{cmd}_cooldowns[name] = now",
            ])

        if snd_fx:
            lines.append(f'        minetest.sound_play("{snd_fx}", {{to_player = name, gain = 1.0}})')

        lines.extend([
            "        local args = {}",
            '        for word in (param or ""):gmatch("%S+") do',
            "            table.insert(args, word)",
            "        end",
            '        local sub = args[1] and args[1]:lower() or ""',
        ])

        if self.subcommands:
            for idx, sub in enumerate(self.subcommands):
                cond_kw = "if" if idx == 0 else "elseif"
                lines.append(f'        {cond_kw} sub == "{sub.sub_name}" then')
                lines.extend(
                    self._compile_sub_action_lines(
                        sub.action_type, sub.action_value, sub.feedback_msg, self.linked_formspec_name, "            "
                    )
                )
            lines.append("        end")

        for idx, arg in enumerate(self.arguments, start=1):
            vname = f"arg_{arg.name}"
            raw_expr = f"args[{idx}]"
            default_lit = f'"{arg.default_val}"' if arg.default_val else "nil"
            if arg.arg_type == "int":
                num_def = arg.default_val if arg.default_val.lstrip("-").isdigit() else "0"
                lines.append(f"        local {vname} = tonumber({raw_expr}) or {num_def if not arg.required else 'nil'}")
            elif arg.arg_type == "player":
                lines.append(f"        local {vname} = {raw_expr} and minetest.get_player_by_name({raw_expr}) or nil")
            elif arg.arg_type == "pos":
                lines.append(f"        local {vname} = {raw_expr} and minetest.string_to_pos({raw_expr}) or player:get_pos()")
            else:
                lines.append(f"        local {vname} = {raw_expr} or {default_lit}")

            if arg.required:
                lines.extend([
                    f"        if not {vname} then",
                    f'            return false, "❌ Argument requis manquant : {arg.format_syntax()}"',
                    "        end",
                ])

        if act_idx == 0:
            lines.extend([
                f'        if custom_gui_show_{cmd} then',
                f'            custom_gui_show_{cmd}(player, param)',
                "        else",
                f'            minetest.show_formspec(name, "{self.linked_formspec_name}", custom_formspec_string or "formspec_version[6]size[11,9.5]")',
                "        end",
            ])
        elif act_idx == 2:
            lines.append(f'        player:get_inventory():add_item("main", "{extra_val or "default:diamond 5"}")')
        elif act_idx == 3:
            lines.append(f'        local target_pos = minetest.string_to_pos("{extra_val}") or {{x=0, y=10, z=0}}')
            lines.append("        player:set_pos(target_pos)")
        elif act_idx == 4:
            lines.extend([
                "        local ppos = player:get_pos()",
                "        local dir = player:get_look_dir()",
                f'        minetest.add_entity({{x=ppos.x+dir.x*2.2, y=ppos.y+0.5, z=ppos.z+dir.z*2.2}}, "{extra_val or "mon_mod:renard_bleu"}")',
            ])
        elif act_idx == 5:
            hp_val = int(extra_val) if extra_val.lstrip("-").isdigit() else 20
            lines.append(f"        player:set_hp(player:get_hp() + ({hp_val}))")

        if feedback:
            lines.append(f'        return true, "{feedback}"')
        else:
            lines.append("        return true")

        lines.extend([
            "    end,",
            "})",
        ])
        return "\n".join(lines)

    def _refresh_lua_preview(self):
        if self._updating_ui:
            return
        cmd = self.inp_name.text().strip().lstrip("/") or "commande"
        if not self.inp_test_cmd.text().startswith(f"/{cmd}"):
            first_sub = f" {self.subcommands[0].sub_name}" if self.subcommands else ""
            self.inp_test_cmd.setText(f"/{cmd}{first_sub}")
        self._refresh_subcommands_list()
        code = self.generate_lua_code()
        self.lua_preview.setPlainText(code)
        self.commandUpdated.emit(code)

    def _simulate_command_execution(self):
        typed = self.inp_test_cmd.text().strip()
        tokens = typed.lstrip("/").split()
        privs = ", ".join(self._collect_privs_list()) or "aucun"

        self.chat_log.appendPlainText(f"\n> {typed}")
        self.chat_log.appendPlainText(f"[Privilèges requis : {privs}] -> Validé ✓")

        args_tokens = tokens[1:] if len(tokens) > 1 else []
        sub_token = args_tokens[0].lower() if args_tokens else ""

        for sub in self.subcommands:
            if sub.sub_name == sub_token:
                self.chat_log.appendPlainText(
                    f"[Sous-Commande '{sub.sub_name}'] Action = {sub.action_type} ({sub.action_value})"
                )
                if sub.feedback_msg:
                    self.chat_log.appendPlainText(f"[Serveur -> Player1] {sub.feedback_msg}")
                return

        for idx, arg in enumerate(self.arguments):
            if arg.required and idx >= len(args_tokens):
                self.chat_log.appendPlainText(f"[Erreur Syntaxe] ❌ Argument requis manquant : {arg.format_syntax()}")
                return

        act_text = self.combo_action.currentText()
        feedback = self.inp_chat_feedback.text().strip()
        self.chat_log.appendPlainText(f"[Action Principale] {act_text}")
        if feedback:
            self.chat_log.appendPlainText(f"[Serveur -> Player1] {feedback}")