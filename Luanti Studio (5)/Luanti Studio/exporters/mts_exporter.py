# -*- coding: utf-8 -*-
"""
exporters/mts_exporter.py
Compilateur complet de Mod Luanti / Minetest (Mis à jour Tâche 4) :
- Export des Items avancés (register_tool, register_craftitem, Armes 3D posables au clic droit, Projectile magique, Soin, Particules)
- Blocs 3D animés sans Z-fighting (drawtype = "airlike" + entité + LBM de restauration)
- Export des icônes 3D/2D avec contour Pixel-Art et cadre de rareté.
"""

import os
import struct
import zlib
from typing import Dict, List, Tuple

from engine.animation.timeline_data import ensure_timeline_data


class MtsExporter:
    """Exportateur binaire MTS et Compilateur de Mod Luanti In-Game."""

    def export_voxels_to_mts(self, voxels: Dict[Tuple[int, int, int], str], filepath: str) -> bool:
        if not voxels:
            return False

        xs = [k[0] for k in voxels.keys()]
        ys = [k[1] for k in voxels.keys()]
        zs = [k[2] for k in voxels.keys()]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        min_z, max_z = min(zs), max(zs)

        size_x = max_x - min_x + 1
        size_y = max_y - min_y + 1
        size_z = max_z - min_z + 1

        node_names = ["air"]
        name_to_id = {"air": 0}
        for n in voxels.values():
            if n not in name_to_id:
                name_to_id[n] = len(node_names)
                node_names.append(n)

        param0_list, param1_list, param2_list = [], [], []
        for z in range(min_z, max_z + 1):
            for y in range(min_y, max_y + 1):
                for x in range(min_x, max_x + 1):
                    n = voxels.get((x, y, z), "air")
                    param0_list.append(name_to_id[n])
                    param1_list.append(255)
                    param2_list.append(0)

        header = b"MTSM" + struct.pack(">HHHH", 4, size_x, size_y, size_z)
        slice_probs = bytes([127] * size_y)
        name_table = struct.pack(">H", len(node_names))
        for n in node_names:
            enc = n.encode("utf-8")
            name_table += struct.pack(">H", len(enc)) + enc

        raw_blocks = (
            b"".join(struct.pack(">H", v) for v in param0_list)
            + bytes(param1_list)
            + bytes(param2_list)
        )
        compressed = zlib.compress(raw_blocks)

        with open(filepath, "wb") as f:
            f.write(header + slice_probs + name_table + compressed)
        return True

    def export_voxels_to_lua_script(self, voxels: Dict[Tuple[int, int, int], str], filepath: str):
        lines = ["-- Script de placement de structure Voxel Luanti Studio", "local V = {"]
        for (x, y, z), node in voxels.items():
            lines.append(f'    {{x = {x}, y = {y}, z = {z}, name = "{node}"}},')
        lines.extend([
            "}",
            "minetest.register_chatcommand('placer_monde', {",
            "    description = 'Place la structure Voxel autour du joueur',",
            "    func = function(name)",
            "        local p = minetest.get_player_by_name(name)",
            "        if not p then return false end",
            "        local o = vector.round(p:get_pos())",
            "        for _, b in ipairs(V) do",
            "            minetest.set_node({x=o.x+b.x, y=o.y+b.y, z=o.z+b.z}, {name=b.name})",
            "        end",
            "        return true, 'Structure Voxel placée !'",
            "    end",
            "})",
        ])
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    @staticmethod
    def _export_animated_obj_frames(mdata, models_dir: str, base_mesh_prefix: str) -> Dict[str, List[str]]:
        tl = ensure_timeline_data(mdata)
        clip_meshes: Dict[str, List[str]] = {}
        num_steps = 8

        for clip_name, clip in tl.clips.items():
            mesh_list = []
            span = max(1, clip.end_frame - clip.start_frame)
            for s in range(num_steps):
                frame_val = clip.start_frame + (span * s) / float(num_steps)
                overrides = {}
                for bname in mdata.bones.keys():
                    overrides[bname] = tl.evaluate_bone_pose(clip, bname, frame_val)
                obj_filename = f"{base_mesh_prefix}_{clip_name}_{s}.obj"
                mdata.export_to_obj(os.path.join(models_dir, obj_filename), bone_overrides=overrides)
                mesh_list.append(obj_filename)
            clip_meshes[clip_name] = mesh_list
        return clip_meshes

    @staticmethod
    def export_complete_luanti_mod(
        folder_path: str,
        mod_name: str,
        assets_by_category: dict,
        command_lua: str,
        formspec_lua: str,
        gui_textures: dict,
        voxels: Dict[Tuple[int, int, int], str],
        void_world: bool = True,
    ) -> str:
        os.makedirs(folder_path, exist_ok=True)
        tex_dir = os.path.join(folder_path, "textures")
        models_dir = os.path.join(folder_path, "models")
        schem_dir = os.path.join(folder_path, "schematics")
        os.makedirs(tex_dir, exist_ok=True)
        os.makedirs(models_dir, exist_ok=True)
        os.makedirs(schem_dir, exist_ok=True)

        with open(os.path.join(folder_path, "mod.conf"), "w", encoding="utf-8") as f:
            f.write(
                f"name = {mod_name}\n"
                f"title = {mod_name.capitalize()} (Luanti Studio)\n"
                f"description = Mod 3D généré par Luanti Studio\n"
                f"optional_depends = default\n"
            )

        for tname, qimg in gui_textures.items():
            qimg.save(os.path.join(tex_dir, tname), "PNG")

        mts_exporter = MtsExporter()
        mts_exporter.export_voxels_to_mts(voxels, os.path.join(schem_dir, "studio_world.mts"))

        lua_lines = [
            f"-- ============================================================================",
            f"-- MOD LUANTI GÉNÉRÉ PAR LUANTI STUDIO : {mod_name}",
            f"-- ============================================================================\n",
        ]

        if void_world:
            lua_lines.extend([
                "minetest.register_on_mapgen_init(function(mgparams)",
                '    minetest.set_mapgen_setting("mg_name", "singlenode", true)',
                "end)\n",
            ])

        # A. BLOCS 3D
        for block_asset in assets_by_category.get("Blocks", []):
            mdata = block_asset.ensure_model_data()
            short_id = block_asset.identifier.split(":")[-1].strip() or "bloc"
            full_id = f"{mod_name}:{short_id}"
            base_prefix = f"{mod_name}_{short_id}"

            uv_tex_file = f"{base_prefix}_uv.png"
            icon_tex_file = f"{base_prefix}_icon.png"
            base_obj_file = f"{base_prefix}.obj"

            mdata.texture_image.save(os.path.join(tex_dir, uv_tex_file), "PNG")
            mdata.render_isometric_icon(64, draw_egg_badge=False).save(os.path.join(tex_dir, icon_tex_file), "PNG")
            mdata.export_to_obj(os.path.join(models_dir, base_obj_file), bone_overrides=None)

            cbox = mdata.get_bounding_box_in_blocks()
            cbox_str = f"{{{cbox[0]}, {cbox[1]}, {cbox[2]}, {cbox[3]}, {cbox[4]}, {cbox[5]}}}"

            groups = "cracky = 2, oddly_breakable_by_hand = 2"
            if not block_asset.in_creative_inventory:
                groups += ", not_in_creative_inventory = 1"

            drawtype_val = "airlike" if mdata.animate_in_game else "mesh"

            lua_lines.extend([
                f"-- === BLOC 3D : {block_asset.display_name} ({full_id}) ===",
                "local node_def = {",
                f'    description = "{block_asset.display_name}",',
                f'    drawtype = "{drawtype_val}",',
                f'    mesh = "{base_obj_file}",',
                f'    tiles = {{"{uv_tex_file}"}},',
                f'    inventory_image = "{icon_tex_file}",',
                f'    wield_image = "{icon_tex_file}",',
                '    paramtype = "light",',
                '    paramtype2 = "facedir",',
                '    sunlight_propagates = true,',
                '    backface_culling = false,',
                f"    light_source = {max(0, min(14, mdata.light_source))},",
                f'    selection_box = {{type = "fixed", fixed = {cbox_str}}},',
                f'    collision_box = {{type = "fixed", fixed = {cbox_str}}},',
                f"    groups = {{{groups}}},",
                "}",
            ])

            if mdata.animate_in_game:
                clip_meshes = MtsExporter._export_animated_obj_frames(mdata, models_dir, base_prefix)
                first_clip = next(iter(clip_meshes.values()), [base_obj_file])
                frames_lua = ", ".join(f'"{m}"' for m in first_clip)

                anim_ent_name = f"{full_id}_anim_entity"
                lua_lines.extend([
                    f'minetest.register_entity("{anim_ent_name}", {{',
                    "    initial_properties = {",
                    '        visual = "mesh",',
                    f'        mesh = "{first_clip[0]}",',
                    f'        textures = {{"{uv_tex_file}"}},',
                    "        visual_size = {x = 10, y = 10, z = 10},",
                    "        physical = false,",
                    "        pointable = false,",
                    "        backface_culling = false,",
                    "    },",
                    f"    _frames = {{{frames_lua}}},",
                    "    _timer = 0,",
                    "    _idx = 1,",
                    "    on_step = function(self, dtime)",
                    "        self._timer = self._timer + dtime",
                    "        if self._timer >= 0.10 then",
                    "            self._timer = 0",
                    "            self._idx = (self._idx % #self._frames) + 1",
                    "            self.object:set_properties({mesh = self._frames[self._idx]})",
                    "        end",
                    "    end,",
                    "})",
                    "node_def.on_construct = function(pos)",
                    f'    minetest.add_entity(pos, "{anim_ent_name}")',
                    "end",
                    "node_def.on_destruct = function(pos)",
                    "    for _, obj in ipairs(minetest.get_objects_inside_radius(pos, 0.65)) do",
                    "        local ent = obj:get_luaentity()",
                    f'        if ent and ent.name == "{anim_ent_name}" then obj:remove() end',
                    "    end",
                    "end",
                    f'minetest.register_lbm({{',
                    f'    name = "{full_id}_respawn_anim",',
                    f'    nodenames = {{"{full_id}"}},',
                    "    run_at_every_load = true,",
                    "    action = function(pos, node)",
                    "        local found = false",
                    "        for _, obj in ipairs(minetest.get_objects_inside_radius(pos, 0.65)) do",
                    "            local ent = obj:get_luaentity()",
                    f'            if ent and ent.name == "{anim_ent_name}" then found = true; break end',
                    "        end",
                    f'        if not found then minetest.add_entity(pos, "{anim_ent_name}") end',
                    "    end,",
                    "})",
                ])

            if block_asset.lua_code.strip():
                lua_lines.append(block_asset.lua_code)

            lua_lines.append(f'minetest.register_node("{full_id}", node_def)\n')

        # B. ITEMS, ARMES & OUTILS 3D (TÂCHE 4 COMPLÈTE)
        for item_asset in assets_by_category.get("Items", []):
            mdata = item_asset.ensure_model_data()
            short_id = item_asset.identifier.split(":")[-1].strip() or "item"
            full_id = f"{mod_name}:{short_id}"
            base_prefix = f"{mod_name}_{short_id}"

            uv_tex_file = f"{base_prefix}_uv.png"
            icon_tex_file = f"{base_prefix}_icon.png"
            base_obj_file = f"{base_prefix}.obj"

            mdata.texture_image.save(os.path.join(tex_dir, uv_tex_file), "PNG")
            mdata.render_isometric_icon(64, draw_egg_badge=False).save(os.path.join(tex_dir, icon_tex_file), "PNG")
            mdata.export_to_obj(os.path.join(models_dir, base_obj_file), bone_overrides=None, y_offset_px=-4.0)

            groups = ""
            if not item_asset.in_creative_inventory:
                groups = "not_in_creative_inventory = 1"

            dmg = max(1, mdata.attack_damage)
            wsx, wsy, wsz = mdata.wield_scale[0], mdata.wield_scale[1], mdata.wield_scale[2]
            uses = max(1, mdata.tool_uses)

            # Si le projectile magique est activé, enregistrer l'entité projectile 3D
            proj_ent_name = f"{full_id}_projectile"
            if mdata.item_shoot_projectile:
                lua_lines.extend([
                    f'minetest.register_entity("{proj_ent_name}", {{',
                    "    initial_properties = {",
                    '        visual = "mesh",',
                    f'        mesh = "{base_obj_file}",',
                    f'        textures = {{"{uv_tex_file}"}},',
                    "        visual_size = {x = 5, y = 5, z = 5},",
                    "        physical = true,",
                    "        collide_with_objects = true,",
                    "        collisionbox = {-0.2, -0.2, -0.2, 0.2, 0.2, 0.2},",
                    "        glow = 12,",
                    "    },",
                    "    _shooter = nil,",
                    "    _life = 0,",
                    "    on_step = function(self, dtime, moveresult)",
                    "        self._life = self._life + dtime",
                    "        local pos = self.object:get_pos()",
                    "        if not pos or self._life > 4.0 then self.object:remove(); return end",
                    "        for _, obj in ipairs(minetest.get_objects_inside_radius(pos, 1.4)) do",
                    "            if obj ~= self.object and (not obj:is_player() or obj:get_player_name() ~= self._shooter) then",
                    f"                obj:punch(self.object, 1.0, {{full_punch_interval=1.0, damage_groups={{fleshy={dmg}}}}}, nil)",
                    "                self.object:remove()",
                    "                return",
                    "            end",
                    "        end",
                    "        if moveresult and moveresult.collides then self.object:remove() end",
                    "    end,",
                    "})",
                ])

            # Si l'item est en mode "placeable_3d", on enregistre aussi son nœud 3D décoratif posable au clic droit
            placed_node_id = f"{full_id}_placed_3d"
            if mdata.item_kind == "placeable_3d":
                lua_lines.extend([
                    f'minetest.register_node("{placed_node_id}", {{',
                    f'    description = "{item_asset.display_name} (Posé)",',
                    '    drawtype = "mesh",',
                    f'    mesh = "{base_obj_file}",',
                    f'    tiles = {{"{uv_tex_file}"}},',
                    f'    inventory_image = "{icon_tex_file}",',
                    '    paramtype = "light",',
                    '    paramtype2 = "facedir",',
                    '    sunlight_propagates = true,',
                    '    walkable = false,',
                    '    backface_culling = false,',
                    f'    drop = "{full_id}",',
                    "    groups = {dig_immediate = 3, not_in_creative_inventory = 1},",
                    "})",
                ])

            groupcaps_lines = []
            if mdata.mine_cracky > 0:
                groupcaps_lines.append(
                    f"            cracky = {{times = {{[1]=1.6, [2]=0.8, [3]=0.4}}, uses = {uses}, maxlevel = {mdata.mine_cracky}}},"
                )
            if mdata.mine_choppy > 0:
                groupcaps_lines.append(
                    f"            choppy = {{times = {{[1]=1.7, [2]=0.9, [3]=0.45}}, uses = {uses}, maxlevel = {mdata.mine_choppy}}},"
                )
            if mdata.mine_snappy > 0:
                groupcaps_lines.append(
                    f"            snappy = {{times = {{[1]=1.4, [2]=0.7, [3]=0.25}}, uses = {uses}, maxlevel = {mdata.mine_snappy}}},"
                )
            if mdata.mine_crumbly > 0:
                groupcaps_lines.append(
                    f"            crumbly = {{times = {{[1]=1.5, [2]=0.75, [3]=0.35}}, uses = {uses}, maxlevel = {mdata.mine_crumbly}}},"
                )

            lua_lines.extend([
                f"-- === ITEM / ARME : {item_asset.display_name} ({full_id}) ===",
                "local item_def = {",
                f'    description = "{item_asset.display_name}",',
                f'    inventory_image = "{icon_tex_file}",',
                f'    wield_image = "{icon_tex_file}",',
                f"    wield_scale = {{x = {wsx:.2f}, y = {wsy:.2f}, z = {wsz:.2f}}},",
                f"    range = {mdata.tool_range:.1f},",
                "    tool_capabilities = {",
                f"        full_punch_interval = {mdata.punch_interval:.2f},",
                "        max_drop_level = 1,",
                "        groupcaps = {",
                *groupcaps_lines,
                "        },",
                f"        damage_groups = {{fleshy = {dmg}}},",
                "    },",
                f"    groups = {{{groups}}},",
                "}",
            ])

            # Pouvoirs spéciaux au clic droit (on_secondary_use / on_place)
            if mdata.item_shoot_projectile or mdata.item_heal_hp != 0 or mdata.item_kind == "placeable_3d":
                lua_lines.extend([
                    "local function _studio_item_rightclick(itemstack, user, pointed_thing)",
                    "    if not user or not user:is_player() then return itemstack end",
                    "    local ppos = user:get_pos()",
                ])
                if mdata.item_heal_hp != 0:
                    lua_lines.append(f"    user:set_hp(user:get_hp() + ({mdata.item_heal_hp}))")
                if mdata.item_hit_particles:
                    lua_lines.append(
                        f'    minetest.add_particlespawner({{amount=16, time=0.25, minpos=ppos, maxpos={{x=ppos.x,y=ppos.y+1.5,z=ppos.z}}, texture="{icon_tex_file}"}})'
                    )
                if mdata.item_shoot_projectile:
                    lua_lines.extend([
                        "    local dir = user:get_look_dir()",
                        "    local sp = {x = ppos.x + dir.x * 1.2, y = ppos.y + 1.4 + dir.y, z = ppos.z + dir.z * 1.2}",
                        f'    local obj = minetest.add_entity(sp, "{proj_ent_name}")',
                        "    if obj then",
                        "        obj:set_velocity({x = dir.x * 20, y = dir.y * 20, z = dir.z * 20})",
                        "        obj:get_luaentity()._shooter = user:get_player_name()",
                        "    end",
                    ])
                if mdata.item_kind == "placeable_3d":
                    lua_lines.extend([
                        "    if pointed_thing and pointed_thing.above then",
                        f'        minetest.set_node(pointed_thing.above, {{name = "{placed_node_id}"}})',
                        "    end",
                    ])
                lua_lines.extend([
                    "    return itemstack",
                    "end",
                    "item_def.on_secondary_use = _studio_item_rightclick",
                    "item_def.on_place = _studio_item_rightclick",
                ])

            if item_asset.lua_code.strip():
                lua_lines.append(item_asset.lua_code)

            reg_fn = "register_craftitem" if mdata.item_kind == "craftitem" else "register_tool"
            lua_lines.append(f'minetest.{reg_fn}("{full_id}", item_def)\n')

        # C. MOBS 3D + IA
        for mob_asset in assets_by_category.get("Mobs", []):
            mdata = mob_asset.ensure_model_data()
            short_id = mob_asset.identifier.split(":")[-1].strip() or "mob"
            full_id = f"{mod_name}:{short_id}"
            base_prefix = f"{mod_name}_{short_id}"

            uv_tex_file = f"{base_prefix}_uv.png"
            egg_icon_file = f"{base_prefix}_egg.png"
            base_obj_file = f"{base_prefix}.obj"

            mdata.texture_image.save(os.path.join(tex_dir, uv_tex_file), "PNG")
            mdata.render_isometric_icon(64, draw_egg_badge=True).save(os.path.join(tex_dir, egg_icon_file), "PNG")
            mdata.export_to_obj(os.path.join(models_dir, base_obj_file), bone_overrides=None)

            clip_meshes = MtsExporter._export_animated_obj_frames(mdata, models_dir, base_prefix)
            stand_frames = clip_meshes.get("stand") or [base_obj_file]
            walk_frames = clip_meshes.get("walk") or stand_frames
            punch_frames = clip_meshes.get("punch") or walk_frames

            stand_lua = ", ".join(f'"{m}"' for m in stand_frames)
            walk_lua = ", ".join(f'"{m}"' for m in walk_frames)
            punch_lua = ", ".join(f'"{m}"' for m in punch_frames)

            cbox = mdata.get_bounding_box_in_blocks()
            cbox_str = f"{{{cbox[0]}, {cbox[1]}, {cbox[2]}, {cbox[3]}, {cbox[4]}, {cbox[5]}}}"

            hp_max = max(1, mdata.max_hp)
            speed = max(0.5, mdata.move_speed)
            dmg = max(1, mdata.attack_damage)
            ai_mode = mdata.ai_behavior
            drop_item = mdata.drop_item

            lua_lines.extend([
                f"-- === MOB 3D & IA : {mob_asset.display_name} ({full_id}) ===",
                "local entity_def = {",
                "    initial_properties = {",
                '        physical = true,',
                '        collide_with_objects = true,',
                f"        collisionbox = {cbox_str},",
                f"        selectionbox = {cbox_str},",
                '        visual = "mesh",',
                f'        mesh = "{base_obj_file}",',
                f'        textures = {{"{uv_tex_file}"}},',
                "        visual_size = {x = 10, y = 10, z = 10},",
                "        backface_culling = false,",
                "        makes_footstep_sound = true,",
                f"        hp_max = {hp_max},",
                f'        nametag = "{mob_asset.display_name} [{hp_max}/{hp_max} PV]",',
                '        nametag_color = "#86efac",',
                "    },",
                f'    _ai_mode = "{ai_mode}",',
                f"    _speed = {speed},",
                f"    _damage = {dmg},",
                f'    _drop = "{drop_item}",',
                "    _state = 'stand',",
                "    _ai_timer = 0,",
                "    _anim_timer = 0,",
                "    _attack_timer = 0,",
                "    _frame_idx = 1,",
                "    _yaw = 0,",
                "    _anim_meshes = {",
                f"        stand = {{{stand_lua}}},",
                f"        walk = {{{walk_lua}}},",
                f"        punch = {{{punch_lua}}},",
                "    },",
                "",
                "    on_activate = function(self, staticdata, dtime_s)",
                "        self.object:set_armor_groups({fleshy = 100})",
                "        self.object:set_acceleration({x = 0, y = -9.81, z = 0})",
                "        self._yaw = math.random() * math.pi * 2",
                "        self.object:set_yaw(self._yaw)",
                "    end,",
                "",
                "    on_step = function(self, dtime)",
                "        local pos = self.object:get_pos()",
                "        if not pos then return end",
                "        local vel = self.object:get_velocity() or {x=0, y=0, z=0}",
                "        self._ai_timer = self._ai_timer + dtime",
                "        self._anim_timer = self._anim_timer + dtime",
                "        self._attack_timer = self._attack_timer + dtime",
                "",
                "        local nearest_player = nil",
                "        local min_dist = 999",
                "        for _, player in ipairs(minetest.get_connected_players()) do",
                "            local ppos = player:get_pos()",
                "            if ppos then",
                "                local d = vector.distance(pos, ppos)",
                "                if d < min_dist then min_dist = d; nearest_player = player end",
                "            end",
                "        end",
                "",
                "        if self._ai_mode == 'static' then",
                "            self._state = 'stand'",
                "            self.object:set_velocity({x = 0, y = vel.y, z = 0})",
                "        elseif self._ai_mode == 'hostile' and nearest_player and min_dist < 14 then",
                "            local ppos = nearest_player:get_pos()",
                "            local dir = vector.direction(pos, ppos)",
                "            self._yaw = minetest.dir_to_yaw(dir)",
                "            self.object:set_yaw(self._yaw)",
                "            if min_dist <= 2.1 then",
                "                self._state = 'punch'",
                "                self.object:set_velocity({x = 0, y = vel.y, z = 0})",
                "                if self._attack_timer >= 1.0 then",
                "                    self._attack_timer = 0",
                "                    nearest_player:punch(self.object, 1.0, {full_punch_interval=1.0, damage_groups={fleshy=self._damage}}, nil)",
                "                end",
                "            else",
                "                self._state = 'walk'",
                "                self.object:set_velocity({x = dir.x * self._speed, y = vel.y, z = dir.z * self._speed})",
                "            end",
                "        elseif self._ai_mode == 'follower' and nearest_player and min_dist < 16 and min_dist > 2.5 then",
                "            local ppos = nearest_player:get_pos()",
                "            local dir = vector.direction(pos, ppos)",
                "            self._yaw = minetest.dir_to_yaw(dir)",
                "            self.object:set_yaw(self._yaw)",
                "            self._state = 'walk'",
                "            self.object:set_velocity({x = dir.x * self._speed, y = vel.y, z = dir.z * self._speed})",
                "        else",
                "            if self._ai_timer >= 2.8 then",
                "                self._ai_timer = 0",
                "                if math.random(1, 3) == 1 then",
                "                    self._state = 'stand'",
                "                else",
                "                    self._state = 'walk'",
                "                    self._yaw = self._yaw + (math.random() - 0.5) * 2.2",
                "                    self.object:set_yaw(self._yaw)",
                "                end",
                "            end",
                "            if self._state == 'walk' then",
                "                local dir = minetest.yaw_to_dir(self._yaw)",
                "                self.object:set_velocity({x = dir.x * self._speed, y = vel.y, z = dir.z * self._speed})",
                "                local front_pos = {x = pos.x + dir.x * 0.9, y = pos.y - 0.2, z = pos.z + dir.z * 0.9}",
                "                local front_node = minetest.get_node_or_nil(front_pos)",
                "                if front_node and front_node.name ~= 'air' and math.abs(vel.y) < 0.2 then",
                "                    self.object:set_velocity({x = dir.x * self._speed, y = 6.2, z = dir.z * self._speed})",
                "                end",
                "            else",
                "                self.object:set_velocity({x = 0, y = vel.y, z = 0})",
                "            end",
                "        end",
                "",
                "        if self._anim_timer >= 0.10 then",
                "            self._anim_timer = 0",
                "            local frames = self._anim_meshes[self._state] or self._anim_meshes['stand']",
                "            if frames and #frames > 0 then",
                "                self._frame_idx = (self._frame_idx % #frames) + 1",
                "                self.object:set_properties({mesh = frames[self._frame_idx]})",
                "            end",
                "        end",
                "    end,",
                "",
                "    on_punch = function(self, puncher, time_from_last_punch, tool_capabilities, dir, damage)",
                "        local hp = math.max(0, self.object:get_hp() - (damage or 2))",
                f'        self.object:set_properties({{nametag = "{mob_asset.display_name} [" .. hp .. "/{hp_max} PV]", nametag_color = "#f87171"}})',
                "        if dir then",
                "            self.object:add_velocity({x = dir.x * 4, y = 3.5, z = dir.z * 4})",
                "        end",
                "        if hp <= 0 then",
                "            local pos = self.object:get_pos()",
                "            if pos and self._drop ~= '' then minetest.add_item(pos, self._drop) end",
                "        end",
                "    end,",
                "}",
            ])

            if mob_asset.lua_code.strip():
                lua_lines.append(mob_asset.lua_code)

            lua_lines.append(f'minetest.register_entity("{full_id}", entity_def)\n')

            if mob_asset.generate_spawn_egg and mob_asset.in_creative_inventory:
                lua_lines.extend([
                    f'minetest.register_craftitem("{full_id}_egg", {{',
                    f'    description = "Œuf : {mob_asset.display_name}",',
                    f'    inventory_image = "{egg_icon_file}",',
                    "    on_place = function(itemstack, placer, pointed_thing)",
                    "        if pointed_thing.above then",
                    "            local spawn_pos = {x = pointed_thing.above.x, y = pointed_thing.above.y + 0.5, z = pointed_thing.above.z}",
                    f'            minetest.add_entity(spawn_pos, "{full_id}")',
                    "        end",
                    "        return itemstack",
                    "    end,",
                    "})\n",
                ])

        # D. PLACEMENT AUTOMATIQUE DU MONDE VOXEL & BÂTON D'INVOCATION
        lua_lines.append("-- === STRUCTURE VOXEL DU MODULE WORLD ===")
        lua_lines.append("local STUDIO_VOXEL_STRUCTURE = {")
        if voxels:
            for (vx, vy, vz), nname in voxels.items():
                lua_lines.append(f'    {{x = {vx}, y = {vy}, z = {vz}, name = "{nname}"}},')
        else:
            for gx in range(-2, 3):
                for gz in range(-2, 3):
                    lua_lines.append(f'    {{x = {gx}, y = 0, z = {gz}, name = "default:stonebrick"}},')

        max_struct_y = max((k[1] for k in voxels.keys()), default=0) + 2

        lua_lines.extend([
            "}",
            "local function place_studio_structure(origin)",
            "    for _, b in ipairs(STUDIO_VOXEL_STRUCTURE) do",
            "        minetest.set_node({x = origin.x + b.x, y = origin.y + b.y, z = origin.z + b.z}, {name = b.name})",
            "    end",
            "end",
            "",
            f'minetest.register_craftitem("{mod_name}:baton_structure_voxel", {{',
            '    description = "🏗️ Bâton d\'Invocation du Monde Voxel (Clic Droit sur un bloc)",',
            '    inventory_image = "default_stick.png^[colorize:#38bdf8:160",',
            "    on_place = function(itemstack, placer, pointed_thing)",
            "        if pointed_thing.above then",
            "            place_studio_structure(pointed_thing.above)",
            "            if placer and placer:is_player() then",
            '                minetest.chat_send_player(placer:get_player_name(), "[Luanti Studio] Structure Voxel placée avec succès !")',
            "            end",
            "        end",
            "        return itemstack",
            "    end,",
            "})",
            "",
            "minetest.register_chatcommand('placer_monde', {",
            "    description = 'Place la structure Voxel créée dans Luanti Studio autour du joueur',",
            "    func = function(name)",
            "        local p = minetest.get_player_by_name(name)",
            "        if not p then return false end",
            "        place_studio_structure(vector.round(p:get_pos()))",
            "        return true, '[Luanti Studio] Structure Voxel générée autour de vous !'",
            "    end,",
            "})",
        ])

        if void_world:
            lua_lines.extend([
                "",
                "local _studio_world_placed = false",
                "minetest.register_on_joinplayer(function(player)",
                "    local pname = player:get_player_name()",
                "    local privs = minetest.get_player_privs(pname)",
                "    privs.fly = true; privs.fast = true; privs.noclip = true; privs.give = true",
                "    minetest.set_player_privs(pname, privs)",
                f"    player:set_pos({{x = 0, y = {max_struct_y}, z = 0}})",
                "    minetest.after(0.5, function()",
                "        if not _studio_world_placed then",
                "            _studio_world_placed = true",
                "            place_studio_structure({x = 0, y = 0, z = 0})",
                "        end",
                "        if player and player:is_player() then",
                f"            player:set_pos({{x = 0, y = {max_struct_y}, z = 0}})",
                '            minetest.chat_send_player(pname, "[Luanti Studio] Monde Voxel généré en (0,0,0) ! Privilèges fly/fast accordés.")',
                "        end",
                "    end)",
                "end)\n",
            ])

        lua_lines.append(formspec_lua or "")
        lua_lines.append("\n")
        lua_lines.append(command_lua or "")

        for cmd_asset in assets_by_category.get("Commands", []):
            if cmd_asset.lua_code.strip():
                lua_lines.append(cmd_asset.lua_code)

        init_path = os.path.join(folder_path, "init.lua")
        with open(init_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lua_lines))

        return init_path