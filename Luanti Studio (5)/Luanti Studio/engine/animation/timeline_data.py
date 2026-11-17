# -*- coding: utf-8 -*-
"""
engine/animation/timeline_data.py
Structures de données de la Timeline d'Animation avec sérialisation JSON complète
(Clips, Pistes par Bone, Images Clés / Keyframes, Interpolation et tables Lua Luanti).
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

try:
    from PyQt6.QtCore import QObject, pyqtSignal
except ImportError:
    from PyQt5.QtCore import QObject, pyqtSignal

from engine.model_loader.model_data import ModelData, ModelBone


INTERPOLATION_MODES = ("smooth", "linear", "step")


@dataclass
class BoneKeyframe:
    """Image clé (Keyframe) stockant la pose d'un Bone à une frame précise."""
    frame: int
    rotation: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # RX, RY, RZ en degrés
    position: List[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])  # Offset X, Y, Z
    interp: str = "smooth"  # "smooth", "linear", "step"

    def copy(self) -> "BoneKeyframe":
        return BoneKeyframe(
            frame=self.frame,
            rotation=list(self.rotation),
            position=list(self.position),
            interp=self.interp,
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame": int(self.frame),
            "rotation": list(self.rotation),
            "position": list(self.position),
            "interp": self.interp,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "BoneKeyframe":
        return cls(
            frame=int(d.get("frame", 0)),
            rotation=list(d.get("rotation", [0.0, 0.0, 0.0])),
            position=list(d.get("position", [0.0, 0.0, 0.0])),
            interp=str(d.get("interp", "smooth")),
        )


@dataclass
class AnimationClip:
    """Clip d'animation nommé (ex: stand, walk, run, punch, float)."""
    name: str
    fps: int = 24
    start_frame: int = 0
    end_frame: int = 40
    loop: bool = True
    tracks: Dict[str, List[BoneKeyframe]] = field(default_factory=dict)

    def get_bone_track(self, bone_name: str) -> List[BoneKeyframe]:
        return self.tracks.setdefault(bone_name, [])

    def set_keyframe(
        self,
        bone_name: str,
        frame: int,
        rotation: List[float],
        position: List[float],
        interp: str = "smooth",
    ) -> BoneKeyframe:
        track = self.get_bone_track(bone_name)
        frame = max(0, int(frame))
        for kf in track:
            if kf.frame == frame:
                kf.rotation = [round(float(v), 2) for v in rotation]
                kf.position = [round(float(v), 2) for v in position]
                kf.interp = interp
                return kf

        new_kf = BoneKeyframe(
            frame=frame,
            rotation=[round(float(v), 2) for v in rotation],
            position=[round(float(v), 2) for v in position],
            interp=interp,
        )
        track.append(new_kf)
        track.sort(key=lambda k: k.frame)
        if frame > self.end_frame:
            self.end_frame = frame
        return new_kf

    def get_keyframe_at(self, bone_name: str, frame: int) -> Optional[BoneKeyframe]:
        for kf in self.tracks.get(bone_name, []):
            if kf.frame == int(frame):
                return kf
        return None

    def remove_keyframe(self, bone_name: str, frame: int) -> bool:
        track = self.tracks.get(bone_name, [])
        before = len(track)
        self.tracks[bone_name] = [kf for kf in track if kf.frame != int(frame)]
        return len(self.tracks[bone_name]) < before

    def move_keyframe(self, bone_name: str, old_frame: int, new_frame: int) -> Optional[BoneKeyframe]:
        new_frame = max(0, int(new_frame))
        if old_frame == new_frame:
            return self.get_keyframe_at(bone_name, old_frame)
        kf = self.get_keyframe_at(bone_name, old_frame)
        if not kf:
            return None
        self.remove_keyframe(bone_name, new_frame)
        kf.frame = new_frame
        self.tracks[bone_name].sort(key=lambda k: k.frame)
        if new_frame > self.end_frame:
            self.end_frame = new_frame
        return kf

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "fps": int(self.fps),
            "start_frame": int(self.start_frame),
            "end_frame": int(self.end_frame),
            "loop": bool(self.loop),
            "tracks": {
                bname: [kf.to_dict() for kf in kfs]
                for bname, kfs in self.tracks.items()
            },
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AnimationClip":
        clip = cls(
            name=str(d.get("name", "walk")),
            fps=int(d.get("fps", 24)),
            start_frame=int(d.get("start_frame", 0)),
            end_frame=int(d.get("end_frame", 40)),
            loop=bool(d.get("loop", True)),
        )
        raw_tracks = d.get("tracks", {})
        for bname, kf_list in raw_tracks.items():
            clip.tracks[bname] = [BoneKeyframe.from_dict(k) for k in kf_list]
            clip.tracks[bname].sort(key=lambda item: item.frame)
        return clip


class TimelineData(QObject):
    """
    Gestionnaire complet des Clips d'animation et de l'évaluation temps réel sur ModelData.
    """
    timelineChanged = pyqtSignal()
    frameChanged = pyqtSignal(float)
    clipChanged = pyqtSignal(str)
    keyframeSelected = pyqtSignal(str, int)

    def __init__(self, model_data: ModelData):
        super().__init__()
        self.model_data = model_data
        self.clips: Dict[str, AnimationClip] = {}
        self.current_clip_name: str = "walk"
        self.current_frame: float = 0.0
        self.auto_key: bool = True
        self.selected_keyframe: Optional[Tuple[str, int]] = None
        self._clipboard_keyframe: Optional[BoneKeyframe] = None

        self.build_default_clips_for_category(model_data.category)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_clip_name": self.current_clip_name,
            "auto_key": self.auto_key,
            "clips": {cname: clip.to_dict() for cname, clip in self.clips.items()},
        }

    def load_from_dict(self, d: Dict[str, Any]):
        if not d or not isinstance(d, dict):
            return
        raw_clips = d.get("clips", {})
        if raw_clips:
            self.clips = {
                cname: AnimationClip.from_dict(cdata)
                for cname, cdata in raw_clips.items()
            }
        self.auto_key = bool(d.get("auto_key", True))
        cur_name = d.get("current_clip_name", "")
        if cur_name in self.clips:
            self.current_clip_name = cur_name
        elif self.clips:
            self.current_clip_name = next(iter(self.clips.keys()))

    def get_current_clip(self) -> AnimationClip:
        if self.current_clip_name not in self.clips:
            if self.clips:
                self.current_clip_name = next(iter(self.clips.keys()))
            else:
                self.clips["stand"] = AnimationClip("stand", fps=24, start_frame=0, end_frame=40)
                self.current_clip_name = "stand"
        return self.clips[self.current_clip_name]

    def set_current_clip(self, clip_name: str):
        if clip_name in self.clips:
            self.current_clip_name = clip_name
            clip = self.clips[clip_name]
            self.current_frame = float(clip.start_frame)
            self.evaluate_at_frame(self.current_frame)
            self.clipChanged.emit(clip_name)
            self.timelineChanged.emit()

    @staticmethod
    def _interpolate_channel(v0: float, v1: float, alpha: float, mode: str) -> float:
        if mode == "step":
            return v0
        if mode == "smooth":
            alpha = (1.0 - math.cos(alpha * math.pi)) * 0.5
        return v0 + (v1 - v0) * alpha

    def evaluate_bone_pose(self, clip: AnimationClip, bone_name: str, frame: float) -> Tuple[List[float], List[float]]:
        track = clip.tracks.get(bone_name, [])
        if not track:
            return [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]

        if len(track) == 1 or frame <= track[0].frame:
            return list(track[0].rotation), list(track[0].position)

        if frame >= track[-1].frame:
            return list(track[-1].rotation), list(track[-1].position)

        for i in range(len(track) - 1):
            k0 = track[i]
            k1 = track[i + 1]
            if k0.frame <= frame <= k1.frame:
                span = max(1e-5, float(k1.frame - k0.frame))
                alpha = (frame - k0.frame) / span
                rot = [
                    round(self._interpolate_channel(k0.rotation[c], k1.rotation[c], alpha, k0.interp), 2)
                    for c in range(3)
                ]
                pos = [
                    round(self._interpolate_channel(k0.position[c], k1.position[c], alpha, k0.interp), 2)
                    for c in range(3)
                ]
                return rot, pos

        return list(track[-1].rotation), list(track[-1].position)

    def evaluate_at_frame(self, frame: float):
        clip = self.get_current_clip()
        self.current_frame = max(0.0, min(float(clip.end_frame), float(frame)))

        for bname, bone in self.model_data.bones.items():
            rot, pos = self.evaluate_bone_pose(clip, bname, self.current_frame)
            bone.rotation = rot
            bone.position = pos

        self.model_data.modelChanged.emit()
        self.frameChanged.emit(self.current_frame)

    def record_keyframe_for_bone(self, bone_name: str, frame: Optional[int] = None, interp: str = "smooth"):
        if bone_name not in self.model_data.bones:
            return
        bone: ModelBone = self.model_data.bones[bone_name]
        target_frame = int(round(self.current_frame)) if frame is None else int(frame)
        clip = self.get_current_clip()
        clip.set_keyframe(bone_name, target_frame, bone.rotation, bone.position, interp=interp)
        self.selected_keyframe = (bone_name, target_frame)
        self.timelineChanged.emit()
        self.keyframeSelected.emit(bone_name, target_frame)

    def record_all_bones_keyframe(self, frame: Optional[int] = None):
        target_frame = int(round(self.current_frame)) if frame is None else int(frame)
        clip = self.get_current_clip()
        for bname, bone in self.model_data.bones.items():
            clip.set_keyframe(bname, target_frame, bone.rotation, bone.position)
        self.timelineChanged.emit()

    def copy_selected_keyframe(self):
        if not self.selected_keyframe:
            return
        bname, f = self.selected_keyframe
        kf = self.get_current_clip().get_keyframe_at(bname, f)
        if kf:
            self._clipboard_keyframe = kf.copy()

    def paste_keyframe_at_current_frame(self):
        if not self._clipboard_keyframe:
            return
        bname = self.model_data.selected_bone_name or "root"
        target_f = int(round(self.current_frame))
        clip = self.get_current_clip()
        clip.set_keyframe(
            bname,
            target_f,
            self._clipboard_keyframe.rotation,
            self._clipboard_keyframe.position,
            self._clipboard_keyframe.interp,
        )
        self.evaluate_at_frame(target_f)
        self.timelineChanged.emit()

    def build_default_clips_for_category(self, category: str):
        self.clips.clear()

        if category == "Mobs":
            walk = AnimationClip("walk", fps=24, start_frame=0, end_frame=40, loop=True)
            walk.set_keyframe("root", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            walk.set_keyframe("root", 10, [2.0, 0.0, 0.0], [0.0, 0.6, 0.0])
            walk.set_keyframe("root", 20, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            walk.set_keyframe("root", 30, [2.0, 0.0, 0.0], [0.0, 0.6, 0.0])
            walk.set_keyframe("root", 40, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])

            walk.set_keyframe("head_bone", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            walk.set_keyframe("head_bone", 20, [6.0, 0.0, 0.0], [0.0, 0.3, 0.0])
            walk.set_keyframe("head_bone", 40, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])

            walk.set_keyframe("tail_bone", 0, [-18.0, -16.0, 0.0], [0.0, 0.0, 0.0])
            walk.set_keyframe("tail_bone", 20, [-12.0, 16.0, 0.0], [0.0, 0.0, 0.0])
            walk.set_keyframe("tail_bone", 40, [-18.0, -16.0, 0.0], [0.0, 0.0, 0.0])

            for leg_a in ("leg_fl_bone", "leg_br_bone"):
                walk.set_keyframe(leg_a, 0, [28.0, 0.0, 0.0], [0.0, 0.0, 0.0])
                walk.set_keyframe(leg_a, 20, [-28.0, 0.0, 0.0], [0.0, 0.0, 0.0])
                walk.set_keyframe(leg_a, 40, [28.0, 0.0, 0.0], [0.0, 0.0, 0.0])

            for leg_b in ("leg_fr_bone", "leg_bl_bone"):
                walk.set_keyframe(leg_b, 0, [-28.0, 0.0, 0.0], [0.0, 0.0, 0.0])
                walk.set_keyframe(leg_b, 20, [28.0, 0.0, 0.0], [0.0, 0.0, 0.0])
                walk.set_keyframe(leg_b, 40, [-28.0, 0.0, 0.0], [0.0, 0.0, 0.0])

            stand = AnimationClip("stand", fps=20, start_frame=0, end_frame=40, loop=True)
            stand.set_keyframe("root", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("root", 20, [0.0, 0.0, 0.0], [0.0, 0.4, 0.0])
            stand.set_keyframe("root", 40, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("head_bone", 0, [0.0, -8.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("head_bone", 20, [4.0, 8.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("head_bone", 40, [0.0, -8.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("tail_bone", 0, [-18.0, -10.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("tail_bone", 20, [-18.0, 10.0, 0.0], [0.0, 0.0, 0.0])
            stand.set_keyframe("tail_bone", 40, [-18.0, -10.0, 0.0], [0.0, 0.0, 0.0])

            punch = AnimationClip("punch", fps=24, start_frame=0, end_frame=24, loop=False)
            punch.set_keyframe("root", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            punch.set_keyframe("root", 8, [-18.0, 0.0, 0.0], [0.0, 1.5, 1.5])
            punch.set_keyframe("root", 14, [15.0, 0.0, 0.0], [0.0, 0.0, 3.0])
            punch.set_keyframe("root", 24, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            punch.set_keyframe("head_bone", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            punch.set_keyframe("head_bone", 12, [25.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            punch.set_keyframe("head_bone", 24, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])

            self.clips["walk"] = walk
            self.clips["stand"] = stand
            self.clips["punch"] = punch
            self.current_clip_name = "walk"

        elif category == "Blocks":
            spin = AnimationClip("idle_spin", fps=24, start_frame=0, end_frame=48, loop=True)
            spin.set_keyframe("crystal_bone", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            spin.set_keyframe("crystal_bone", 24, [12.0, 180.0, 0.0], [0.0, 1.8, 0.0])
            spin.set_keyframe("crystal_bone", 48, [0.0, 360.0, 0.0], [0.0, 0.0, 0.0])
            self.clips["idle_spin"] = spin
            self.current_clip_name = "idle_spin"

        else:
            swing = AnimationClip("wield_swing", fps=30, start_frame=0, end_frame=30, loop=True)
            swing.set_keyframe("root", 0, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            swing.set_keyframe("root", 10, [-25.0, 0.0, 0.0], [0.0, 1.0, 0.0])
            swing.set_keyframe("root", 18, [55.0, 0.0, 0.0], [0.0, -0.5, 1.5])
            swing.set_keyframe("root", 30, [0.0, 0.0, 0.0], [0.0, 0.0, 0.0])
            self.clips["wield_swing"] = swing
            self.current_clip_name = "wield_swing"

    def generate_luanti_lua_animation_table(self) -> str:
        lines = [
            "-- Table d'animations Luanti générée automatiquement",
            "animations = {"
        ]
        cursor = 0
        for cname, clip in self.clips.items():
            length = max(1, clip.end_frame - clip.start_frame)
            x_start = cursor
            y_end = cursor + length
            lines.append(
                f'    ["{cname}"] = {{x = {x_start}, y = {y_end}, speed = {clip.fps}, loop = {str(clip.loop).lower()}}},'
            )
            cursor = y_end + 5
        lines.append("}")
        return "\n".join(lines)


def ensure_timeline_data(model_data: ModelData) -> TimelineData:
    """Récupère ou attache une instance TimelineData directement sur un ModelData."""
    tl = getattr(model_data, "timeline_data", None)
    if tl is None or not isinstance(tl, TimelineData):
        tl = TimelineData(model_data)
        raw_saved = getattr(model_data, "_pending_timeline_dict", None)
        if raw_saved:
            tl.load_from_dict(raw_saved)
            setattr(model_data, "_pending_timeline_dict", None)
        setattr(model_data, "timeline_data", tl)
    return tl