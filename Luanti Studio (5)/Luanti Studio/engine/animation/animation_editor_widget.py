# -*- coding: utf-8 -*-
"""
engine/animation/animation_editor_widget.py
Workbench 3 : Éditeur d'Animation Haute Visibilité avec vraie Timeline multipiste (Dope Sheet),
ajout/déplacement d'Images Clés (Keyframes), mode Auto-Key et aperçu 3D Luanti temps réel.
"""

from typing import List, Optional, Tuple

try:
    from PyQt6.QtCore import Qt, QTimer, QRectF, QPointF
    from PyQt6.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QLinearGradient
    )
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QGroupBox, QInputDialog, QMenu, QDialog, QPlainTextEdit
    )
except ImportError:
    from PyQt5.QtCore import Qt, QTimer, QRectF, QPointF
    from PyQt5.QtGui import (
        QPainter, QColor, QPen, QBrush, QFont, QPolygonF, QLinearGradient
    )
    from PyQt5.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QFrame,
        QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
        QCheckBox, QGroupBox, QInputDialog, QMenu, QDialog, QPlainTextEdit
    )

from engine.model_loader.model_data import ModelData
from engine.renderer.panda_viewport import PandaViewport
from engine.animation.timeline_data import TimelineData, ensure_timeline_data, BoneKeyframe


class TimelineDopeSheetWidget(QWidget):
    """
    Vraie Timeline & Dope Sheet haute visibilité :
    - Colonne des Bones à gauche
    - Règle temporelle graduée en haut avec curseur de lecture rouge (Playhead)
    - Pistes horizontales avec barres d'interpolation et losanges d'Images Clés (Keyframes)
    - Clic/Glisser sur la règle : Scrubbing temps réel
    - Clic/Glisser sur un losange : Déplacement temporel d'une Image Clé
    - Double-clic sur une case : Ajout immédiat d'une Image Clé
    """
    HEADER_HEIGHT = 34
    ROW_HEIGHT = 32
    LEFT_COLUMN_WIDTH = 195

    def __init__(self, timeline_data: TimelineData, parent_editor: "AnimationEditorWidget"):
        super().__init__(parent_editor)
        self.timeline_data = timeline_data
        self.editor = parent_editor
        self.setMinimumHeight(230)
        self.setMouseTracking(True)

        self.px_per_frame = 18.0
        self.scroll_x_frames = 0.0

        self._dragging_playhead = False
        self._dragging_keyframe: Optional[Tuple[str, int]] = None  # (bone_name, current_frame_of_kf)
        self._hover_cell: Optional[Tuple[str, int]] = None

    def set_timeline_data(self, timeline_data: TimelineData):
        self.timeline_data = timeline_data
        self.update()

    def _bone_list(self) -> List[str]:
        return list(self.timeline_data.model_data.bones.keys())

    def _frame_to_x(self, frame: float) -> float:
        return self.LEFT_COLUMN_WIDTH + (frame - self.scroll_x_frames) * self.px_per_frame + 12.0

    def _x_to_frame(self, x: float) -> int:
        raw = (x - self.LEFT_COLUMN_WIDTH - 12.0) / self.px_per_frame + self.scroll_x_frames
        clip = self.timeline_data.get_current_clip()
        return max(0, min(clip.end_frame, int(round(raw))))

    def _y_to_bone_index(self, y: float) -> int:
        if y < self.HEADER_HEIGHT:
            return -1
        return int((y - self.HEADER_HEIGHT) // self.ROW_HEIGHT)

    # =========================================================================
    # RENDU HAUTE VISIBILITÉ DE LA TIMELINE & DES KEYFRAMES
    # =========================================================================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        w = self.width()
        h = self.height()
        clip = self.timeline_data.get_current_clip()
        bones = self._bone_list()
        cur_frame_int = int(round(self.timeline_data.current_frame))

        # 1. Fond général sombre à fort contraste
        painter.fillRect(self.rect(), QColor("#111319"))

        # 2. Dessin des lignes de pistes (1 ligne par Bone)
        for idx, bname in enumerate(bones):
            ry = self.HEADER_HEIGHT + idx * self.ROW_HEIGHT
            is_sel_bone = (bname == self.timeline_data.model_data.selected_bone_name)

            # Fond de la piste
            if is_sel_bone:
                row_bg = QColor("#1e293b")
            else:
                row_bg = QColor("#151821") if idx % 2 == 0 else QColor("#181c26")
            painter.fillRect(QRectF(self.LEFT_COLUMN_WIDTH, ry, w - self.LEFT_COLUMN_WIDTH, self.ROW_HEIGHT), row_bg)

            # Séparateur horizontal
            painter.setPen(QPen(QColor("#262b38"), 1.0))
            painter.drawLine(0, int(ry + self.ROW_HEIGHT), w, int(ry + self.ROW_HEIGHT))

        # 3. Grille verticale des Frames (0 .. clip.end_frame)
        for f in range(0, clip.end_frame + 1):
            fx = self._frame_to_x(f)
            if fx < self.LEFT_COLUMN_WIDTH or fx > w:
                continue

            if f % 10 == 0:
                painter.setPen(QPen(QColor("#334155"), 1.3))
            elif f % 5 == 0:
                painter.setPen(QPen(QColor("#262f3f"), 1.0))
            else:
                painter.setPen(QPen(QColor("#1c202b"), 1.0))
            painter.drawLine(int(fx), self.HEADER_HEIGHT, int(fx), h)

        # Surbrillance de la colonne de la frame active
        cur_x = self._frame_to_x(self.timeline_data.current_frame)
        if cur_x >= self.LEFT_COLUMN_WIDTH:
            painter.fillRect(
                QRectF(cur_x - self.px_per_frame * 0.5, self.HEADER_HEIGHT, self.px_per_frame, h - self.HEADER_HEIGHT),
                QColor(239, 68, 68, 28)
            )

        # 4. Dessin des barres d'interpolation et des losanges d'Images Clés (Keyframes)
        for idx, bname in enumerate(bones):
            ry = self.HEADER_HEIGHT + idx * self.ROW_HEIGHT
            cy = ry + self.ROW_HEIGHT * 0.5
            track = clip.tracks.get(bname, [])

            # Barre d'interpolation reliant les clés consécutives
            if len(track) >= 2:
                for i in range(len(track) - 1):
                    x0 = self._frame_to_x(track[i].frame)
                    x1 = self._frame_to_x(track[i + 1].frame)
                    if x1 >= self.LEFT_COLUMN_WIDTH and x0 <= w:
                        bar_rect = QRectF(max(float(self.LEFT_COLUMN_WIDTH), x0), cy - 3.5, min(float(w), x1) - max(float(self.LEFT_COLUMN_WIDTH), x0), 7.0)
                        painter.fillRect(bar_rect, QColor(56, 189, 248, 65))

            # Losanges d'Images Clés (Keyframes)
            for kf in track:
                kx = self._frame_to_x(kf.frame)
                if kx < self.LEFT_COLUMN_WIDTH or kx > w:
                    continue

                is_selected_kf = (self.timeline_data.selected_keyframe == (bname, kf.frame))
                is_on_playhead = (kf.frame == cur_frame_int)

                self._draw_keyframe_diamond(painter, kx, cy, is_selected_kf, is_on_playhead, kf.interp)

        # 5. Colonne gauche (Noms des Bones + Nombre de clés)
        painter.fillRect(QRectF(0, 0, self.LEFT_COLUMN_WIDTH, h), QColor("#12151c"))
        painter.setPen(QPen(QColor("#2e3646"), 1.5))
        painter.drawLine(self.LEFT_COLUMN_WIDTH, 0, self.LEFT_COLUMN_WIDTH, h)

        for idx, bname in enumerate(bones):
            ry = self.HEADER_HEIGHT + idx * self.ROW_HEIGHT
            is_sel_bone = (bname == self.timeline_data.model_data.selected_bone_name)
            if is_sel_bone:
                painter.fillRect(QRectF(0, ry, self.LEFT_COLUMN_WIDTH - 2, self.ROW_HEIGHT), QColor("#1d4ed8"))

            painter.setPen(QColor("#ffffff") if is_sel_bone else QColor("#cbd5e1"))
            painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold if is_sel_bone else QFont.Weight.Normal))
            kf_count = len(clip.tracks.get(bname, []))
            painter.drawText(
                QRectF(10, ry, self.LEFT_COLUMN_WIDTH - 16, self.ROW_HEIGHT),
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                f"🦴 {bname}  ({kf_count} clés)"
            )

        # 6. En-tête supérieur (Règle graduée des Frames)
        painter.fillRect(QRectF(0, 0, w, self.HEADER_HEIGHT), QColor("#0d1016"))
        painter.setPen(QPen(QColor("#2e3646"), 1.5))
        painter.drawLine(0, self.HEADER_HEIGHT, w, self.HEADER_HEIGHT)

        painter.setPen(QColor("#60a5fa"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Weight.Bold))
        painter.drawText(
            QRectF(10, 0, self.LEFT_COLUMN_WIDTH - 14, self.HEADER_HEIGHT),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            "PISTES BONES / FRAMES"
        )

        painter.setFont(QFont("Consolas", 9, QFont.Weight.Bold))
        for f in range(0, clip.end_frame + 1):
            fx = self._frame_to_x(f)
            if fx < self.LEFT_COLUMN_WIDTH or fx > w:
                continue
            if f % 5 == 0:
                painter.setPen(QPen(QColor("#94a3b8"), 1.4))
                painter.drawLine(int(fx), self.HEADER_HEIGHT - 10, int(fx), self.HEADER_HEIGHT)
                painter.setPen(QColor("#e2e8f0"))
                painter.drawText(QRectF(fx - 18, 2, 36, 18), Qt.AlignmentFlag.AlignCenter, str(f))
            else:
                painter.setPen(QPen(QColor("#475569"), 1.0))
                painter.drawLine(int(fx), self.HEADER_HEIGHT - 5, int(fx), self.HEADER_HEIGHT)

        # 7. Curseur de lecture rouge vif (Playhead)
        if cur_x >= self.LEFT_COLUMN_WIDTH:
            painter.setPen(QPen(QColor("#ef4444"), 2.2))
            painter.drawLine(int(cur_x), 0, int(cur_x), h)

            # Tête du curseur avec numéro de frame
            badge = QPolygonF([
                QPointF(cur_x - 16, 2),
                QPointF(cur_x + 16, 2),
                QPointF(cur_x + 16, 19),
                QPointF(cur_x, 28),
                QPointF(cur_x - 16, 19),
            ])
            painter.setBrush(QBrush(QColor("#ef4444")))
            painter.setPen(QPen(QColor("#fecaca"), 1.2))
            painter.drawPolygon(badge)

            painter.setPen(QColor("#ffffff"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            painter.drawText(QRectF(cur_x - 16, 2, 32, 17), Qt.AlignmentFlag.AlignCenter, str(cur_frame_int))

    def _draw_keyframe_diamond(self, painter: QPainter, cx: float, cy: float, is_selected: bool, is_current: bool, interp: str):
        r = 7.5 if (is_selected or is_current) else 6.2
        diamond = QPolygonF([
            QPointF(cx, cy - r),
            QPointF(cx + r, cy),
            QPointF(cx, cy + r),
            QPointF(cx - r, cy),
        ])

        if is_selected:
            fill = QColor("#facc15")   # Jaune Or vif
            border = QColor("#ffffff")
        elif is_current:
            fill = QColor("#fb923c")   # Orange vif
            border = QColor("#ffffff")
        elif interp == "linear":
            fill = QColor("#22c55e")   # Vert émeraude
            border = QColor("#052e16")
        elif interp == "step":
            fill = QColor("#a855f7")   # Violet
            border = QColor("#3b0764")
        else:
            fill = QColor("#38bdf8")   # Cyan lumineux (Smooth)
            border = QColor("#082f49")

        painter.setBrush(QBrush(fill))
        painter.setPen(QPen(border, 1.6))
        painter.drawPolygon(diamond)

    # =========================================================================
    # INTERACTIONS SOURIS SUR LA TIMELINE (SCRUBBING, DRAG KEYFRAME, DOUBLE-CLIC)
    # =========================================================================
    def _find_keyframe_near_pos(self, pos: QPointF) -> Optional[Tuple[str, int]]:
        bones = self._bone_list()
        idx = self._y_to_bone_index(pos.y())
        if not (0 <= idx < len(bones)):
            return None
        bname = bones[idx]
        clip = self.timeline_data.get_current_clip()
        for kf in clip.tracks.get(bname, []):
            kx = self._frame_to_x(kf.frame)
            if abs(pos.x() - kx) <= 9.0:
                return bname, kf.frame
        return None

    def mousePressEvent(self, event):
        pos = QPointF(event.pos())
        bones = self._bone_list()
        row_idx = self._y_to_bone_index(pos.y())

        # Clic dans la colonne de gauche : sélectionne le Bone
        if pos.x() < self.LEFT_COLUMN_WIDTH:
            if 0 <= row_idx < len(bones):
                self.timeline_data.model_data.select_bone(bones[row_idx])
                self.update()
            return

        if event.button() == Qt.MouseButton.LeftButton:
            # 1. Vérifie si on clique sur un losange d'Image Clé existant
            hit_kf = self._find_keyframe_near_pos(pos)
            if hit_kf is not None and pos.y() >= self.HEADER_HEIGHT:
                bname, kf_frame = hit_kf
                self.timeline_data.model_data.select_bone(bname)
                self.timeline_data.selected_keyframe = (bname, kf_frame)
                self.timeline_data.evaluate_at_frame(kf_frame)
                self.timeline_data.keyframeSelected.emit(bname, kf_frame)
                self._dragging_keyframe = (bname, kf_frame)
                self.update()
                return

            # 2. Sinon : déplace le curseur de lecture (Playhead Scrubbing)
            if 0 <= row_idx < len(bones):
                self.timeline_data.model_data.select_bone(bones[row_idx])
            target_f = self._x_to_frame(pos.x())
            self.timeline_data.selected_keyframe = None
            self.timeline_data.evaluate_at_frame(target_f)
            self._dragging_playhead = True
            self.update()

    def mouseMoveEvent(self, event):
        pos = QPointF(event.pos())

        if self._dragging_keyframe is not None:
            bname, old_frame = self._dragging_keyframe
            new_frame = self._x_to_frame(pos.x())
            if new_frame != old_frame:
                clip = self.timeline_data.get_current_clip()
                moved = clip.move_keyframe(bname, old_frame, new_frame)
                if moved:
                    self._dragging_keyframe = (bname, new_frame)
                    self.timeline_data.selected_keyframe = (bname, new_frame)
                    self.timeline_data.evaluate_at_frame(new_frame)
                    self.update()
            return

        if self._dragging_playhead:
            target_f = self._x_to_frame(pos.x())
            self.timeline_data.evaluate_at_frame(target_f)
            self.update()

    def mouseReleaseEvent(self, event):
        self._dragging_playhead = False
        self._dragging_keyframe = None

    def mouseDoubleClickEvent(self, event):
        """Double-cliquer sur une ligne de Bone insère immédiatement une Image Clé à cette frame !"""
        pos = QPointF(event.pos())
        if pos.x() < self.LEFT_COLUMN_WIDTH or pos.y() < self.HEADER_HEIGHT:
            return
        bones = self._bone_list()
        row_idx = self._y_to_bone_index(pos.y())
        if 0 <= row_idx < len(bones):
            bname = bones[row_idx]
            frame = self._x_to_frame(pos.x())
            self.timeline_data.model_data.select_bone(bname)
            self.timeline_data.evaluate_at_frame(frame)
            self.timeline_data.record_keyframe_for_bone(bname, frame)
            self.update()

    def contextMenuEvent(self, event):
        pos = QPointF(event.pos())
        hit_kf = self._find_keyframe_near_pos(pos)
        menu = QMenu(self)

        act_add = menu.addAction("➕ Insérer Image Clé ici")
        act_copy = menu.addAction("📄 Copier l'Image Clé")
        act_paste = menu.addAction("📋 Coller l'Image Clé au curseur")
        act_del = menu.addAction("🗑️ Supprimer cette Image Clé")
        act_del.setEnabled(hit_kf is not None)

        chosen = menu.exec(event.globalPos())
        if chosen == act_add:
            bname = self.timeline_data.model_data.selected_bone_name or "root"
            self.timeline_data.record_keyframe_for_bone(bname)
        elif chosen == act_copy and hit_kf:
            self.timeline_data.selected_keyframe = hit_kf
            self.timeline_data.copy_selected_keyframe()
        elif chosen == act_paste:
            self.timeline_data.paste_keyframe_at_current_frame()
        elif chosen == act_del and hit_kf:
            bname, f = hit_kf
            self.timeline_data.get_current_clip().remove_keyframe(bname, f)
            self.timeline_data.evaluate_at_frame(self.timeline_data.current_frame)
            self.update()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.12 if delta > 0 else 0.88
        self.px_per_frame = max(8.0, min(42.0, self.px_per_frame * factor))
        self.update()


class AnimationEditorWidget(QWidget):
    """
    Atelier 3 : Animation 3D & Timeline Multipiste avec Images Clés (Keyframes).
    """

    def __init__(self, model_data: Optional[ModelData] = None, parent=None):
        super().__init__(parent)
        self.model_data = model_data or ModelData("Mobs")
        self.timeline_data = ensure_timeline_data(self.model_data)
        self._updating_ui = False

        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self._on_playback_tick)
        self.is_playing = False

        self._build_ui()
        self._connect_signals()
        self._refresh_clip_selector()
        self._refresh_pose_inspector()
        self.timeline_data.evaluate_at_frame(0.0)

    def set_model_data(self, model_data: ModelData):
        self.stop_playback()
        self.model_data = model_data
        self.timeline_data = ensure_timeline_data(model_data)
        self.viewport.set_model_data(model_data)
        self.dope_sheet.set_timeline_data(self.timeline_data)
        self._connect_signals()
        self._refresh_clip_selector()
        self._refresh_pose_inspector()
        self.timeline_data.evaluate_at_frame(self.timeline_data.current_frame)

    def _connect_signals(self):
        try:
            self.model_data.selectionChanged.connect(self._on_bone_selection_changed)
            self.timeline_data.frameChanged.connect(self._on_frame_changed)
            self.timeline_data.timelineChanged.connect(self._on_timeline_updated)
            self.timeline_data.keyframeSelected.connect(self._on_keyframe_selected)
        except Exception:
            pass

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # Splitter Vertical : Haut (Viewport 3D + Pose Inspector) | Bas (Barre Transport + Timeline Dope Sheet)
        v_splitter = QSplitter(Qt.Orientation.Vertical)

        # =====================================================================
        # PARTIE HAUTE : VIEWPORT 3D ANIMÉ + INSPECTEUR DE POSE DU BONE
        # =====================================================================
        top_widget = QWidget()
        top_layout = QHBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        h_splitter = QSplitter(Qt.Orientation.Horizontal)

        # 1. Viewport 3D en mode rotation de Bone directe
        vp_frame = QFrame()
        vp_frame.setProperty("class", "InspectorPanel")
        vp_layout = QVBoxLayout(vp_frame)
        vp_layout.setContentsMargins(6, 6, 6, 6)

        vp_header = QHBoxLayout()
        lbl_vp = QLabel("🎬 APERÇU 3D TEMPS RÉEL (Utilisez le Gizmo 3D ou les curseurs à droite pour poser vos Bones)")
        lbl_vp.setStyleSheet("font-weight: bold; color: #60a5fa;")
        vp_header.addWidget(lbl_vp)
        vp_header.addStretch()

        self.chk_autokey = QCheckBox("🔴 Auto-Key (Enregistrer une Image Clé dès qu'un Bone bouge)")
        self.chk_autokey.setChecked(True)
        self.chk_autokey.setStyleSheet("color: #f87171; font-weight: bold;")
        self.chk_autokey.toggled.connect(self._on_autokey_toggled)
        vp_header.addWidget(self.chk_autokey)
        vp_layout.addLayout(vp_header)

        self.viewport = PandaViewport(self.model_data, interaction_mode="transform", parent=self)
        self.viewport.transform_tool = "rotate"
        self.viewport.transformDragged.connect(self._on_viewport_bone_manipulated)
        vp_layout.addWidget(self.viewport, 1)

        h_splitter.addWidget(vp_frame)

        # 2. Panneau Droit : Pose du Bone à la Frame courante & Clips Luanti
        pose_panel = QFrame()
        pose_panel.setProperty("class", "InspectorPanel")
        pose_layout = QVBoxLayout(pose_panel)
        pose_layout.setContentsMargins(10, 8, 10, 8)
        pose_layout.setSpacing(8)

        # Sélecteur de Bone à animer
        grp_bone = QGroupBox("🦴 Bone en cours d'animation")
        b_layout = QVBoxLayout(grp_bone)
        self.combo_bone = QComboBox()
        self.combo_bone.currentTextChanged.connect(self._on_bone_combo_changed)
        b_layout.addWidget(self.combo_bone)
        pose_layout.addWidget(grp_bone)

        # Rotation RX, RY, RZ du Bone à la frame courante
        self.spn_rot = self._create_xyz_spin_group(
            pose_layout, "Rotation du Bone à cette Frame (RX°, RY°, RZ°)", -180.0, 180.0, 5.0
        )
        # Position Offset X, Y, Z du Bone à la frame courante
        self.spn_pos = self._create_xyz_spin_group(
            pose_layout, "Décalage Position du Bone (X, Y, Z)", -64.0, 64.0, 0.5
        )

        # Type d'interpolation de l'image clé
        interp_row = QHBoxLayout()
        interp_row.addWidget(QLabel("Interpolation :"))
        self.combo_interp = QComboBox()
        self.combo_interp.addItems(["smooth (Douce / Cosinus)", "linear (Linéaire)", "step (Palier constant)"])
        self.combo_interp.currentIndexChanged.connect(self._on_pose_spin_edited)
        interp_row.addWidget(self.combo_interp, 1)
        pose_layout.addLayout(interp_row)

        # Actions rapides sur les Images Clés
        kf_btn_row1 = QHBoxLayout()
        btn_add_kf = QPushButton("🔑 + Image Clé (Bone actif)")
        btn_add_kf.setObjectName("PrimaryButton")
        btn_add_kf.clicked.connect(self._add_keyframe_current_bone)

        btn_add_all = QPushButton("🔑🔑 Clé sur Tous les Bones")
        btn_add_all.clicked.connect(self._add_keyframe_all_bones)

        kf_btn_row1.addWidget(btn_add_kf)
        kf_btn_row1.addWidget(btn_add_all)
        pose_layout.addLayout(kf_btn_row1)

        kf_btn_row2 = QHBoxLayout()
        btn_reset_pose = QPushButton("🔄 Réinitialiser Pose (0°)")
        btn_reset_pose.clicked.connect(self._reset_current_bone_pose)

        btn_del_kf = QPushButton("🗑️ Supprimer Clé")
        btn_del_kf.setObjectName("DangerButton")
        btn_del_kf.clicked.connect(self._delete_current_keyframe)

        kf_btn_row2.addWidget(btn_reset_pose)
        kf_btn_row2.addWidget(btn_del_kf)
        pose_layout.addLayout(kf_btn_row2)

        btn_lua_preview = QPushButton("📜 Voir la Table Lua d'Animations Luanti")
        btn_lua_preview.clicked.connect(self._show_luanti_lua_dialog)
        pose_layout.addWidget(btn_lua_preview)

        pose_layout.addStretch()
        h_splitter.addWidget(pose_panel)
        h_splitter.setSizes([860, 360])

        top_layout.addWidget(h_splitter)
        v_splitter.addWidget(top_widget)

        # =====================================================================
        # PARTIE BASSE : BARRE DE TRANSPORT + TIMELINE DOPE SHEET
        # =====================================================================
        bottom_widget = QFrame()
        bottom_widget.setProperty("class", "InspectorPanel")
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(8, 6, 8, 8)
        bottom_layout.setSpacing(6)

        # Barre de contrôle de lecture et gestion des Clips
        transport = QHBoxLayout()

        self.btn_play = QPushButton("▶ Lecture")
        self.btn_play.setObjectName("PrimaryButton")
        self.btn_play.clicked.connect(self.toggle_playback)
        transport.addWidget(self.btn_play)

        btn_stop = QPushButton("⏹ Stop (Frame 0)")
        btn_stop.clicked.connect(self.stop_playback)
        transport.addWidget(btn_stop)

        btn_prev_kf = QPushButton("⏮ Clé Préc.")
        btn_prev_kf.clicked.connect(self._jump_prev_keyframe)
        transport.addWidget(btn_prev_kf)

        btn_next_kf = QPushButton("⏭ Clé Suiv.")
        btn_next_kf.clicked.connect(self._jump_next_keyframe)
        transport.addWidget(btn_next_kf)

        transport.addWidget(QLabel("Frame :"))
        self.spn_cur_frame = QSpinBox()
        self.spn_cur_frame.setRange(0, 999)
        self.spn_cur_frame.valueChanged.connect(self._on_frame_spin_changed)
        transport.addWidget(self.spn_cur_frame)

        transport.addSpacing(12)
        transport.addWidget(QLabel("🎞️ Clip Luanti :"))
        self.combo_clips = QComboBox()
        self.combo_clips.currentTextChanged.connect(self._on_clip_combo_changed)
        transport.addWidget(self.combo_clips)

        btn_new_clip = QPushButton("➕ Nouveau Clip")
        btn_new_clip.clicked.connect(self._create_new_clip)
        transport.addWidget(btn_new_clip)

        transport.addWidget(QLabel("Fin (Frames) :"))
        self.spn_end_frame = QSpinBox()
        self.spn_end_frame.setRange(5, 600)
        self.spn_end_frame.setValue(40)
        self.spn_end_frame.valueChanged.connect(self._on_clip_settings_changed)
        transport.addWidget(self.spn_end_frame)

        transport.addWidget(QLabel("FPS :"))
        self.spn_fps = QSpinBox()
        self.spn_fps.setRange(1, 60)
        self.spn_fps.setValue(24)
        self.spn_fps.valueChanged.connect(self._on_clip_settings_changed)
        transport.addWidget(self.spn_fps)

        self.chk_loop = QCheckBox("Boucle")
        self.chk_loop.setChecked(True)
        self.chk_loop.toggled.connect(self._on_clip_settings_changed)
        transport.addWidget(self.chk_loop)

        transport.addStretch()
        bottom_layout.addLayout(transport)

        # Timeline Dope Sheet interactive
        self.dope_sheet = TimelineDopeSheetWidget(self.timeline_data, self)
        bottom_layout.addWidget(self.dope_sheet, 1)

        v_splitter.addWidget(bottom_widget)
        v_splitter.setSizes([520, 310])

        root.addWidget(v_splitter)

    def _create_xyz_spin_group(self, parent_layout: QVBoxLayout, title: str, min_v: float, max_v: float, step: float):
        grp = QGroupBox(title)
        row = QHBoxLayout(grp)
        spins = []
        for axis_lbl, col in [("X", "#ef4444"), ("Y", "#22c55e"), ("Z", "#3b82f6")]:
            lbl = QLabel(axis_lbl)
            lbl.setStyleSheet(f"color: {col}; font-weight: bold;")
            spn = QDoubleSpinBox()
            spn.setRange(min_v, max_v)
            spn.setSingleStep(step)
            spn.setDecimals(1)
            spn.valueChanged.connect(self._on_pose_spin_edited)
            row.addWidget(lbl)
            row.addWidget(spn, 1)
            spins.append(spn)
        parent_layout.addWidget(grp)
        return spins

    # =========================================================================
    # GESTION DE LA LECTURE (PLAY / PAUSE / SCRUBBING)
    # =========================================================================
    def toggle_playback(self):
        if self.is_playing:
            self.play_timer.stop()
            self.is_playing = False
            self.btn_play.setText("▶ Lecture")
        else:
            clip = self.timeline_data.get_current_clip()
            interval_ms = max(10, int(1000.0 / max(1, clip.fps)))
            self.play_timer.start(interval_ms)
            self.is_playing = True
            self.btn_play.setText("⏸ Pause")

    def stop_playback(self):
        self.play_timer.stop()
        self.is_playing = False
        self.btn_play.setText("▶ Lecture")
        clip = self.timeline_data.get_current_clip()
        self.timeline_data.evaluate_at_frame(clip.start_frame)

    def _on_playback_tick(self):
        clip = self.timeline_data.get_current_clip()
        next_f = self.timeline_data.current_frame + 1.0
        if next_f > clip.end_frame:
            if clip.loop:
                next_f = float(clip.start_frame)
            else:
                self.stop_playback()
                return
        self.timeline_data.evaluate_at_frame(next_f)

    # =========================================================================
    # SYNCHRONISATION POSE INSPECTOR <-> TIMELINE <-> VIEWPORT 3D
    # =========================================================================
    def _refresh_clip_selector(self):
        self._updating_ui = True
        self.combo_clips.clear()
        for cname in self.timeline_data.clips.keys():
            self.combo_clips.addItem(cname)
        self.combo_clips.setCurrentText(self.timeline_data.current_clip_name)

        clip = self.timeline_data.get_current_clip()
        self.spn_end_frame.setValue(clip.end_frame)
        self.spn_fps.setValue(clip.fps)
        self.chk_loop.setChecked(clip.loop)

        self.combo_bone.clear()
        for bname in self.model_data.bones.keys():
            self.combo_bone.addItem(bname)
        if self.model_data.selected_bone_name:
            self.combo_bone.setCurrentText(self.model_data.selected_bone_name)

        self._updating_ui = False
        self.dope_sheet.update()

    def _refresh_pose_inspector(self):
        self._updating_ui = True
        bname = self.model_data.selected_bone_name or "root"
        if self.combo_bone.currentText() != bname:
            self.combo_bone.setCurrentText(bname)

        bone = self.model_data.bones.get(bname)
        if bone:
            for i in range(3):
                self.spn_rot[i].setValue(bone.rotation[i])
                self.spn_pos[i].setValue(bone.position[i])

        self.spn_cur_frame.setValue(int(round(self.timeline_data.current_frame)))
        self._updating_ui = False

    def _on_bone_selection_changed(self):
        self._refresh_pose_inspector()
        self.dope_sheet.update()

    def _on_frame_changed(self, frame: float):
        self._refresh_pose_inspector()
        self.dope_sheet.update()

    def _on_timeline_updated(self):
        self.dope_sheet.update()

    def _on_keyframe_selected(self, bone_name: str, frame: int):
        clip = self.timeline_data.get_current_clip()
        kf = clip.get_keyframe_at(bone_name, frame)
        if kf:
            self._updating_ui = True
            idx = 0
            if kf.interp == "linear":
                idx = 1
            elif kf.interp == "step":
                idx = 2
            self.combo_interp.setCurrentIndex(idx)
            self._updating_ui = False

    def _current_interp_mode(self) -> str:
        idx = self.combo_interp.currentIndex()
        if idx == 1:
            return "linear"
        if idx == 2:
            return "step"
        return "smooth"

    def _on_pose_spin_edited(self):
        if self._updating_ui:
            return
        bname = self.model_data.selected_bone_name or "root"
        bone = self.model_data.bones.get(bname)
        if not bone:
            return

        for i in range(3):
            bone.rotation[i] = self.spn_rot[i].value()
            bone.position[i] = self.spn_pos[i].value()

        if self.timeline_data.auto_key:
            self.timeline_data.record_keyframe_for_bone(
                bname,
                int(round(self.timeline_data.current_frame)),
                interp=self._current_interp_mode()
            )
        self.model_data.modelChanged.emit()
        self.dope_sheet.update()

    def _on_viewport_bone_manipulated(self):
        """Appelé quand l'utilisateur tourne un Bone directement avec le Gizmo 3D dans le Viewport."""
        bname = self.model_data.selected_bone_name or "root"
        if self.timeline_data.auto_key:
            self.timeline_data.record_keyframe_for_bone(
                bname,
                int(round(self.timeline_data.current_frame)),
                interp=self._current_interp_mode()
            )
        self._refresh_pose_inspector()
        self.dope_sheet.update()

    def _on_bone_combo_changed(self, bname: str):
        if self._updating_ui or not bname:
            return
        self.model_data.select_bone(bname)

    def _on_frame_spin_changed(self, val: int):
        if self._updating_ui:
            return
        self.timeline_data.evaluate_at_frame(float(val))

    def _on_clip_combo_changed(self, cname: str):
        if self._updating_ui or not cname:
            return
        self.timeline_data.set_current_clip(cname)
        self._refresh_clip_selector()

    def _on_clip_settings_changed(self):
        if self._updating_ui:
            return
        clip = self.timeline_data.get_current_clip()
        clip.end_frame = self.spn_end_frame.value()
        clip.fps = self.spn_fps.value()
        clip.loop = self.chk_loop.isChecked()
        if self.is_playing:
            self.play_timer.setInterval(max(10, int(1000.0 / max(1, clip.fps))))
        self.dope_sheet.update()

    def _on_autokey_toggled(self, checked: bool):
        self.timeline_data.auto_key = checked

    def _add_keyframe_current_bone(self):
        bname = self.model_data.selected_bone_name or "root"
        self.timeline_data.record_keyframe_for_bone(bname, interp=self._current_interp_mode())

    def _add_keyframe_all_bones(self):
        self.timeline_data.record_all_bones_keyframe()

    def _reset_current_bone_pose(self):
        bname = self.model_data.selected_bone_name or "root"
        bone = self.model_data.bones.get(bname)
        if bone:
            bone.rotation = [0.0, 0.0, 0.0]
            bone.position = [0.0, 0.0, 0.0]
            if self.timeline_data.auto_key:
                self.timeline_data.record_keyframe_for_bone(bname)
            self._refresh_pose_inspector()
            self.model_data.modelChanged.emit()

    def _delete_current_keyframe(self):
        bname = self.model_data.selected_bone_name or "root"
        cur_f = int(round(self.timeline_data.current_frame))
        clip = self.timeline_data.get_current_clip()
        clip.remove_keyframe(bname, cur_f)
        self.timeline_data.evaluate_at_frame(cur_f)
        self.dope_sheet.update()

    def _jump_prev_keyframe(self):
        bname = self.model_data.selected_bone_name or "root"
        cur_f = int(round(self.timeline_data.current_frame))
        track = self.timeline_data.get_current_clip().tracks.get(bname, [])
        prev_frames = [kf.frame for kf in track if kf.frame < cur_f]
        if prev_frames:
            self.timeline_data.evaluate_at_frame(prev_frames[-1])

    def _jump_next_keyframe(self):
        bname = self.model_data.selected_bone_name or "root"
        cur_f = int(round(self.timeline_data.current_frame))
        track = self.timeline_data.get_current_clip().tracks.get(bname, [])
        next_frames = [kf.frame for kf in track if kf.frame > cur_f]
        if next_frames:
            self.timeline_data.evaluate_at_frame(next_frames[0])

    def _create_new_clip(self):
        name, ok = QInputDialog.getText(self, "Nouveau Clip d'Animation", "Nom du clip (ex: run, die, special_attack) :")
        if ok and name.strip():
            cname = name.strip().replace(" ", "_")
            from engine.animation.timeline_data import AnimationClip
            clip = AnimationClip(cname, fps=24, start_frame=0, end_frame=40, loop=True)
            for bname in self.model_data.bones.keys():
                clip.set_keyframe(bname, 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
                clip.set_keyframe(bname, 40, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            self.timeline_data.clips[cname] = clip
            self.timeline_data.set_current_clip(cname)
            self._refresh_clip_selector()

    def _show_luanti_lua_dialog(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Table d'Animations Lua Luanti")
        dlg.resize(560, 320)
        lay = QVBoxLayout(dlg)
        txt = QPlainTextEdit()
        txt.setPlainText(self.timeline_data.generate_luanti_lua_animation_table())
        lay.addWidget(txt)
        dlg.exec()