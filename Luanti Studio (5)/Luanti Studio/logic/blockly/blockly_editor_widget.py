# -*- coding: utf-8 -*-
"""
logic/blockly/blockly_editor_widget.py
Éditeur logique visuel Blockly 100% natif PyQt6 (QGraphicsScene / QGraphicsView).
Élimine définitivement le crash Windows 0xC0000005 (3221225477) lié à QWebEngineView.
Supporte l'aimantation magnétique des blocs, l'édition des paramètres et la compilation Lua temps réel.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional

try:
    from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
        QListWidgetItem, QGraphicsView, QGraphicsScene, QGraphicsItem,
        QGraphicsObject, QFrame, QLabel, QLineEdit, QComboBox,
        QPushButton, QFormLayout, QMenu
    )
except ImportError:
    from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QPainterPath, QPolygonF
    )
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget,
        QListWidgetItem, QGraphicsView, QGraphicsScene, QGraphicsItem,
        QGraphicsObject, QFrame, QLabel, QLineEdit, QComboBox,
        QPushButton, QFormLayout, QMenu
    )


@dataclass
class BlockTemplate:
    block_id: str
    title: str
    category: str
    is_event: bool  # True = bloc chapeau (déclencheur), False = bloc action empilable
    color_hex: str
    default_params: Dict[str, str] = field(default_factory=dict)
    param_options: Dict[str, List[str]] = field(default_factory=dict)


# Bibliothèque complète des blocs Luanti par catégorie
BLOCK_TEMPLATES: Dict[str, List[BlockTemplate]] = {
    "Mobs": [
        BlockTemplate(
            "mob_event", "🐺 Événement Mob", "Mobs", True, "#9333ea",
            {"event": "on_activate"},
            {"event": ["on_activate", "on_step", "on_punch", "on_rightclick", "on_die"]}
        ),
        BlockTemplate(
            "mob_anim", "🎬 Jouer Animation Mob", "Mobs", False, "#7e22ce",
            {"anim": "walk", "fps": "15"},
            {"anim": ["stand", "walk", "run", "punch", "die"]}
        ),
        BlockTemplate(
            "mob_velocity", "🏃 Définir Vitesse Mob", "Mobs", False, "#6b21a8",
            {"vx": "0", "vy": "0", "vz": "2"}
        ),
        BlockTemplate(
            "mob_drop", "🎁 Faire tomber un Item", "Mobs", False, "#581c87",
            {"item": "default:mese_crystal", "count": "1"}
        ),
    ],
    "Blocks": [
        BlockTemplate(
            "block_event", "🧱 Événement Bloc", "Blocks", True, "#16a34a",
            {"event": "on_rightclick"},
            {"event": ["on_construct", "on_destruct", "on_rightclick", "on_punch", "on_timer"]}
        ),
        BlockTemplate(
            "block_replace", "🔄 Remplacer ce Bloc par", "Blocks", False, "#15803d",
            {"node": "default:mese"}
        ),
        BlockTemplate(
            "block_particles", "✨ Émettre Particules", "Blocks", False, "#166534",
            {"amount": "20", "texture": "default_item_smoke.png"}
        ),
    ],
    "Items": [
        BlockTemplate(
            "item_event", "⚔️ Événement Item", "Items", True, "#ea580c",
            {"event": "on_use"},
            {"event": ["on_use", "on_place", "on_secondary_use"]}
        ),
        BlockTemplate(
            "item_heal", "❤️ Modifier PV du Joueur", "Items", False, "#c2410c",
            {"hp": "4"}
        ),
        BlockTemplate(
            "item_boost", "⚡ Propulser le Joueur", "Items", False, "#9a3412",
            {"vx": "0", "vy": "8", "vz": "12"}
        ),
    ],
    "Commands": [
        BlockTemplate(
            "cmd_event", "⌨️ Quand /commande est tapée", "Commands", True, "#2563eb",
            {"cmd": "boutique", "privs": "interact"}
        ),
        BlockTemplate(
            "gui_show", "🖼️ Ouvrir GUI Personnalisée", "Commands", False, "#1d4ed8",
            {"formname": "mon_mod:custom_gui"}
        ),
        BlockTemplate(
            "gui_btn_event", "🖱️ Quand Bouton GUI cliqué", "Commands", True, "#0284c7",
            {"button_id": "btn_valider"}
        ),
    ],
    "Common": [
        BlockTemplate(
            "chat_send", "💬 Envoyer Message Chat", "Common", False, "#0d9488",
            {"message": "Action exécutée avec succès !"}
        ),
        BlockTemplate(
            "give_item", "🎒 Donner Item au Joueur", "Common", False, "#0f766e",
            {"item": "default:diamond", "count": "1"}
        ),
        BlockTemplate(
            "play_sound", "🔊 Jouer un Son Luanti", "Common", False, "#115e59",
            {"sound": "default_dig_cracky", "gain": "1.0"}
        ),
        BlockTemplate(
            "condition_hp", "🔀 Si PV du joueur > seuil", "Common", False, "#ca8a04",
            {"min_hp": "10"}
        ),
    ]
}


class VisualBlockItem(QGraphicsObject):
    """
    Bloc visuel interactif façon Blockly/Scratch avec encoches de puzzle,
    aimantation magnétique automatique et affichage en direct des paramètres.
    """
    SNAP_DISTANCE = 32.0
    BLOCK_WIDTH = 330.0
    BLOCK_HEIGHT = 64.0

    def __init__(self, template: BlockTemplate, scene_ref: "BlocklyScene"):
        super().__init__()
        self.template = template
        self.scene_ref = scene_ref
        self.params: Dict[str, str] = dict(template.default_params)

        # Chaînage des blocs (parent au-dessus, enfant en dessous)
        self.prev_block: Optional["VisualBlockItem"] = None
        self.next_block: Optional["VisualBlockItem"] = None

        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def boundingRect(self) -> QRectF:
        return QRectF(0, -10, self.BLOCK_WIDTH, self.BLOCK_HEIGHT + 18)

    def _build_puzzle_path(self) -> QPainterPath:
        w = self.BLOCK_WIDTH
        h = self.BLOCK_HEIGHT
        notch_x = 28.0
        notch_w = 34.0
        notch_h = 7.0

        path = QPainterPath()
        if self.template.is_event:
            # Chapeau arrondi en haut pour les blocs Événements (comme dans Scratch/Blockly)
            path.moveTo(0, 12)
            path.quadTo(w * 0.35, -10, w * 0.7, 12)
            path.lineTo(w - 8, 12)
            path.quadTo(w, 12, w, 20)
        else:
            # Encoche femelle en haut pour s'emboîter sous le bloc précédent
            path.moveTo(0, 6)
            path.lineTo(notch_x, 6)
            path.lineTo(notch_x + 6, 6 + notch_h)
            path.lineTo(notch_x + notch_w - 6, 6 + notch_h)
            path.lineTo(notch_x + notch_w, 6)
            path.lineTo(w - 8, 6)
            path.quadTo(w, 6, w, 14)

        # Côté droit et bas avec tenon mâle pour accueillir le bloc suivant
        path.lineTo(w, h - 8)
        path.quadTo(w, h, w - 8, h)
        path.lineTo(notch_x + notch_w, h)
        path.lineTo(notch_x + notch_w - 6, h + notch_h)
        path.lineTo(notch_x + 6, h + notch_h)
        path.lineTo(notch_x, h)
        path.lineTo(8, h)
        path.quadTo(0, h, 0, h - 8)
        path.closeSubpath()
        return path

    def paint(self, painter: QPainter, option, widget=None):
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        path = self._build_puzzle_path()

        base_color = QColor(self.template.color_hex)
        if self.isSelected():
            fill_color = base_color.lighter(120)
            border_pen = QPen(QColor("#facc15"), 2.5)
        else:
            fill_color = base_color
            border_pen = QPen(base_color.darker(140), 1.5)

        painter.setBrush(QBrush(fill_color))
        painter.setPen(border_pen)
        painter.drawPath(path)

        # Titre du bloc
        painter.setPen(QColor("#ffffff"))
        title_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(title_font)
        painter.drawText(QRectF(14, 10, self.BLOCK_WIDTH - 24, 22), Qt.AlignmentFlag.AlignVCenter, self.template.title)

        # Badges des paramètres à l'intérieur du bloc
        param_font = QFont("Consolas", 9, QFont.Weight.Bold)
        painter.setFont(param_font)
        summary_parts = [f"{k}: {v}" for k, v in self.params.items()]
        summary_str = "  |  ".join(summary_parts) if summary_parts else "Aucun paramètre"

        badge_rect = QRectF(14, 34, self.BLOCK_WIDTH - 28, 22)
        painter.setBrush(QBrush(QColor(0, 0, 0, 95)))
        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.0))
        painter.drawRoundedRect(badge_rect, 4, 4)

        painter.setPen(QColor("#e2e8f0"))
        painter.drawText(badge_rect.adjusted(6, 0, -6, 0), Qt.AlignmentFlag.AlignVCenter, summary_str)

    def mousePressEvent(self, event):
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        if event.button() == Qt.MouseButton.LeftButton and self.prev_block is not None:
            # Détache de la chaîne supérieure quand on tire ce bloc
            self.prev_block.next_block = None
            self.prev_block = None
        super().mousePressEvent(event)
        self.scene_ref.blockSelected.emit(self)

    def mouseMoveEvent(self, event):
        super().mouseMoveEvent(event)
        self._move_attached_chain()

    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        super().mouseReleaseEvent(event)
        self._try_magnetic_snap()
        self._move_attached_chain()
        self.scene_ref.requestLuaCompilation.emit()

    def _move_attached_chain(self):
        """Déplace solidairement tous les blocs emboîtés en dessous."""
        curr = self
        while curr.next_block is not None:
            nxt = curr.next_block
            target_pos = curr.pos() + QPointF(0, self.BLOCK_HEIGHT - 6)
            if nxt.pos() != target_pos:
                nxt.setPos(target_pos)
            curr = nxt

    def _try_magnetic_snap(self):
        """Aimante automatiquement ce bloc sous le bloc le plus proche."""
        if self.template.is_event:
            return  # Un bloc événement est toujours en haut d'une pile

        for other in self.scene_ref.blocks:
            if other is self or other.next_block is not None:
                continue
            if self._is_in_my_chain(other):
                continue

            snap_point = other.pos() + QPointF(0, self.BLOCK_HEIGHT - 6)
            dist = (self.pos() - snap_point).manhattanLength()
            if dist <= self.SNAP_DISTANCE:
                self.setPos(snap_point)
                other.next_block = self
                self.prev_block = other
                break

    def _is_in_my_chain(self, candidate: "VisualBlockItem") -> bool:
        curr = self.next_block
        while curr is not None:
            if curr is candidate:
                return True
            curr = curr.next_block
        return False

    def contextMenuEvent(self, event):
        menu = QMenu()
        act_dup = menu.addAction("📄 Dupliquer ce bloc")
        act_del = menu.addAction("🗑️ Supprimer ce bloc")
        chosen = menu.exec(event.screenPos())
        if chosen == act_dup:
            self.scene_ref.duplicate_block(self)
        elif chosen == act_del:
            self.scene_ref.remove_block(self)


class BlocklyScene(QGraphicsScene):
    """Scène graphique contenant les piles de blocs logiques."""
    blockSelected = pyqtSignal(object)
    requestLuaCompilation = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSceneRect(0, 0, 2400, 1800)
        self.blocks: List[VisualBlockItem] = []

    def drawBackground(self, painter: QPainter, rect: QRectF):
        painter.fillRect(rect, QColor("#14161b"))
        grid_step = 24
        left = int(rect.left()) - (int(rect.left()) % grid_step)
        top = int(rect.top()) - (int(rect.top()) % grid_step)

        pen = QPen(QColor("#222631"), 1.0)
        painter.setPen(pen)
        for x in range(left, int(rect.right()), grid_step):
            for y in range(top, int(rect.bottom()), grid_step):
                painter.drawPoint(x, y)

    def add_visual_block(self, template: BlockTemplate, pos: QPointF) -> VisualBlockItem:
        blk = VisualBlockItem(template, self)
        blk.setPos(pos)
        self.addItem(blk)
        self.blocks.append(blk)
        blk._try_magnetic_snap()
        blk._move_attached_chain()
        self.requestLuaCompilation.emit()
        return blk

    def duplicate_block(self, blk: VisualBlockItem):
        new_blk = self.add_visual_block(blk.template, blk.pos() + QPointF(30, 30))
        new_blk.params = dict(blk.params)
        new_blk.update()
        self.requestLuaCompilation.emit()

    def remove_block(self, blk: VisualBlockItem):
        if blk.prev_block:
            blk.prev_block.next_block = blk.next_block
        if blk.next_block:
            blk.next_block.prev_block = blk.prev_block
            blk.next_block._move_attached_chain()
        if blk in self.blocks:
            self.blocks.remove(blk)
        self.removeItem(blk)
        self.blockSelected.emit(None)
        self.requestLuaCompilation.emit()

    def clear_all_blocks(self):
        for b in list(self.blocks):
            self.removeItem(b)
        self.blocks.clear()
        self.blockSelected.emit(None)
        self.requestLuaCompilation.emit()


class BlocklyEditorWidget(QWidget):
    """
    Éditeur visuel de blocs Luanti 100% natif PyQt6.
    Fonctionne pour Mobs, Blocks, Items et Commands sans QWebEngineView.
    """
    codeChanged = pyqtSignal(str)
    lua_code_generated = pyqtSignal(str)

    def __init__(self, category: str = "Mobs", parent=None):
        super().__init__(parent)
        self.current_category = category
        self.selected_block: Optional[VisualBlockItem] = None
        self._last_lua_code = ""
        self._build_ui()
        self.set_category(category, reset_starter=True)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Boîte à outils des Blocs (Gauche)
        toolbox_panel = QFrame()
        toolbox_panel.setProperty("class", "InspectorPanel")
        tb_layout = QVBoxLayout(toolbox_panel)
        tb_layout.setContentsMargins(8, 8, 8, 8)

        lbl_tb = QLabel("🧰 Boîte à Blocs (Clic pour ajouter)")
        lbl_tb.setStyleSheet("font-weight: bold; color: #93c5fd;")
        tb_layout.addWidget(lbl_tb)

        self.toolbox_list = QListWidget()
        self.toolbox_list.itemClicked.connect(self._on_toolbox_item_clicked)
        tb_layout.addWidget(self.toolbox_list, 1)

        btn_clear = QPushButton("🧹 Vider l'espace de travail")
        btn_clear.clicked.connect(lambda: self.scene.clear_all_blocks())
        tb_layout.addWidget(btn_clear)

        splitter.addWidget(toolbox_panel)

        # 2. Canevas Visuel d'assemblage des Blocs (Centre) + Inspecteur de paramètres (Bas)
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        center_layout.setContentsMargins(0, 0, 0, 0)
        center_layout.setSpacing(6)

        self.scene = BlocklyScene(self)
        self.scene.blockSelected.connect(self._on_block_selected)
        self.scene.requestLuaCompilation.connect(self._compile_workspace_to_lua)

        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        center_layout.addWidget(self.view, 1)

        # Barre d'édition rapide des paramètres du bloc sélectionné
        self.param_bar = QFrame()
        self.param_bar.setProperty("class", "InspectorPanel")
        self.param_form = QFormLayout(self.param_bar)
        self.param_form.setContentsMargins(12, 8, 12, 8)
        center_layout.addWidget(self.param_bar)

        splitter.addWidget(center_panel)
        splitter.setSizes([250, 620])
        root.addWidget(splitter)

    def set_category(self, category: str, reset_starter: bool = False):
        """Met à jour la boîte à outils selon la catégorie active (Mobs, Blocks, Items, Commands)."""
        self.current_category = category
        self.toolbox_list.clear()

        cat_templates = BLOCK_TEMPLATES.get(category, BLOCK_TEMPLATES["Mobs"])
        common_templates = BLOCK_TEMPLATES["Common"]

        for tpl in cat_templates + common_templates:
            item = QListWidgetItem(tpl.title)
            item.setData(Qt.ItemDataRole.UserRole, tpl)
            item.setForeground(QBrush(QColor("#f8fafc")))
            item.setBackground(QBrush(QColor(tpl.color_hex)))
            self.toolbox_list.addItem(item)

        if reset_starter:
            self.scene.clear_all_blocks()
            if len(cat_templates) >= 2:
                ev_blk = self.scene.add_visual_block(cat_templates[0], QPointF(60, 50))
                act_blk = self.scene.add_visual_block(
                    cat_templates[1],
                    QPointF(60, 50 + VisualBlockItem.BLOCK_HEIGHT - 6)
                )
                ev_blk.next_block = act_blk
                act_blk.prev_block = ev_blk
                self._on_block_selected(ev_blk)
            self._compile_workspace_to_lua()

    def _on_toolbox_item_clicked(self, item: QListWidgetItem):
        tpl: BlockTemplate = item.data(Qt.ItemDataRole.UserRole)
        if not tpl:
            return

        # Si un bloc est sélectionné et n'a pas de suivant, emboîte directement en dessous !
        if self.selected_block and not tpl.is_event and self.selected_block.next_block is None:
            spawn_pos = self.selected_block.pos() + QPointF(0, VisualBlockItem.BLOCK_HEIGHT - 6)
        else:
            offset = len(self.scene.blocks) * 28
            spawn_pos = QPointF(80 + (offset % 160), 60 + offset)

        new_blk = self.scene.add_visual_block(tpl, spawn_pos)
        self.scene.clearSelection()
        new_blk.setSelected(True)
        self._on_block_selected(new_blk)

    def _on_block_selected(self, blk: Optional[VisualBlockItem]):
        self.selected_block = blk
        while self.param_form.count():
            child = self.param_form.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if blk is None:
            self.param_form.addRow(QLabel("💡 Cliquez sur un bloc pour modifier ses paramètres ou glissez-le pour l'aimanter."))
            return

        header = QLabel(f"⚙️ Paramètres du bloc : {blk.template.title}")
        header.setStyleSheet("font-weight: bold; color: #60a5fa;")
        self.param_form.addRow(header)

        for key, val in blk.params.items():
            options = blk.template.param_options.get(key)
            if options:
                combo = QComboBox()
                combo.addItems(options)
                combo.setCurrentText(val)
                combo.currentTextChanged.connect(lambda v, k=key, b=blk: self._update_block_param(b, k, v))
                self.param_form.addRow(f"{key} :", combo)
            else:
                inp = QLineEdit(val)
                inp.textChanged.connect(lambda v, k=key, b=blk: self._update_block_param(b, k, v))
                self.param_form.addRow(f"{key} :", inp)

    def _update_block_param(self, blk: VisualBlockItem, key: str, value: str):
        blk.params[key] = value
        blk.update()
        self._compile_workspace_to_lua()

    def _compile_workspace_to_lua(self):
        """Compile toutes les piles de blocs commençant par un bloc Événement en code Lua Luanti valide."""
        lines = [
            f"-- Code Lua généré automatiquement par Luanti Studio ({self.current_category})",
            ""
        ]

        # Trouve les têtes de pile (blocs sans parent)
        root_blocks = [b for b in self.scene.blocks if b.prev_block is None]
        root_blocks.sort(key=lambda b: (b.pos().y(), b.pos().x()))

        for root in root_blocks:
            tid = root.template.block_id
            p = root.params

            if tid == "mob_event":
                evt = p.get("event", "on_activate")
                lines.append(f"entity_def.{evt} = function(self, staticdata, dtime_s)")
                lines.append("    local pos = self.object:get_pos()")
                self._compile_chain_body(root.next_block, lines, indent="    ")
                lines.append("end\n")

            elif tid == "block_event":
                evt = p.get("event", "on_rightclick")
                lines.append(f"node_def.{evt} = function(pos, node, player, itemstack, pointed_thing)")
                self._compile_chain_body(root.next_block, lines, indent="    ")
                lines.append("end\n")

            elif tid == "item_event":
                evt = p.get("event", "on_use")
                lines.append(f"item_def.{evt} = function(itemstack, user, pointed_thing)")
                lines.append("    local player = user")
                lines.append("    local pos = user and user:get_pos() or nil")
                self._compile_chain_body(root.next_block, lines, indent="    ")
                lines.append("    return itemstack")
                lines.append("end\n")

            elif tid == "cmd_event":
                cmd = p.get("cmd", "boutique")
                privs = p.get("privs", "interact")
                lines.append(f'minetest.register_chatcommand("{cmd}", {{')
                lines.append(f'    description = "Commande /{cmd}",')
                lines.append(f'    privs = {{{privs} = true}},')
                lines.append("    func = function(name, param)")
                lines.append("        local player = minetest.get_player_by_name(name)")
                self._compile_chain_body(root.next_block, lines, indent="        ")
                lines.append("        return true")
                lines.append("    end")
                lines.append("})\n")

            elif tid == "gui_btn_event":
                btn_id = p.get("button_id", "btn_valider")
                lines.append("minetest.register_on_player_receive_fields(function(player, formname, fields)")
                lines.append(f'    if fields["{btn_id}"] then')
                self._compile_chain_body(root.next_block, lines, indent="        ")
                lines.append("    end")
                lines.append("end)\n")

            else:
                # Bloc action posé seul
                self._compile_chain_body(root, lines, indent="")

        lua_code = "\n".join(lines)
        self._last_lua_code = lua_code
        self.codeChanged.emit(lua_code)
        self.lua_code_generated.emit(lua_code)

    def _compile_chain_body(self, first_block: Optional[VisualBlockItem], lines: List[str], indent: str):
        curr = first_block
        while curr is not None:
            tid = curr.template.block_id
            p = curr.params

            if tid == "mob_anim":
                anim = p.get("anim", "walk")
                fps = p.get("fps", "15")
                lines.append(f'{indent}if self.animations and self.animations["{anim}"] then')
                lines.append(f'{indent}    self.object:set_animation(self.animations["{anim}"], {fps}, 0, true)')
                lines.append(f'{indent}end')

            elif tid == "mob_velocity":
                vx, vy, vz = p.get("vx", "0"), p.get("vy", "0"), p.get("vz", "2")
                lines.append(f"{indent}self.object:set_velocity({{x = {vx}, y = {vy}, z = {vz}}})")

            elif tid == "mob_drop":
                item, count = p.get("item", "default:mese_crystal"), p.get("count", "1")
                lines.append(f'{indent}if pos then minetest.add_item(pos, "{item} {count}") end')

            elif tid == "block_replace":
                node = p.get("node", "default:mese")
                lines.append(f'{indent}minetest.set_node(pos, {{name = "{node}"}})')

            elif tid == "block_particles":
                amt, tex = p.get("amount", "20"), p.get("texture", "default_item_smoke.png")
                lines.append(
                    f'{indent}minetest.add_particlespawner({{amount = {amt}, time = 0.5, '
                    f'minpos = pos, maxpos = pos, texture = "{tex}"}})'
                )

            elif tid == "item_heal":
                hp = p.get("hp", "4")
                lines.append(f"{indent}if player and player:is_player() then player:set_hp(player:get_hp() + ({hp})) end")

            elif tid == "item_boost":
                vx, vy, vz = p.get("vx", "0"), p.get("vy", "8"), p.get("vz", "12")
                lines.append(f"{indent}if player and player:is_player() then player:add_velocity({{x={vx}, y={vy}, z={vz}}}) end")

            elif tid == "gui_show":
                formname = p.get("formname", "mon_mod:custom_gui")
                lines.append(
                    f'{indent}if player then minetest.show_formspec(player:get_player_name(), '
                    f'"{formname}", custom_formspec_string or "size[8,6]label[0.5,0.5;GUI]") end'
                )

            elif tid == "chat_send":
                msg = p.get("message", "Bonjour !").replace('"', '\\"')
                lines.append(
                    f'{indent}if player and player:is_player() then '
                    f'minetest.chat_send_player(player:get_player_name(), "{msg}") '
                    f'else minetest.chat_send_all("{msg}") end'
                )

            elif tid == "give_item":
                item, count = p.get("item", "default:diamond"), p.get("count", "1")
                lines.append(
                    f'{indent}if player and player:is_player() then '
                    f'player:get_inventory():add_item("main", "{item} {count}") end'
                )

            elif tid == "play_sound":
                snd, gain = p.get("sound", "default_dig_cracky"), p.get("gain", "1.0")
                lines.append(f'{indent}minetest.sound_play("{snd}", {{gain = {gain}}})')

            elif tid == "condition_hp":
                min_hp = p.get("min_hp", "10")
                lines.append(f"{indent}if player and player:is_player() and player:get_hp() > {min_hp} then")
                self._compile_chain_body(curr.next_block, lines, indent + "    ")
                lines.append(f"{indent}end")
                break

            curr = curr.next_block

    def refresh_layout(self):
        self.view.viewport().update()

    def get_lua_code(self) -> str:
        return self._last_lua_code