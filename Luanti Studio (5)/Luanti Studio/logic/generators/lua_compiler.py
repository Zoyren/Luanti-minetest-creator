from typing import Any, Dict, List


class BlocklyLuaCompiler:
    """
    Compilateur transformant un arbre de blocs visuels Blockly en code Lua Luanti valide.
    Prend en charge les Mobs, les Blocs (avec Nodeboxes et Timers), les Items (avec Projectiles) et les Commandes/GUI.
    """

    def compile_workspace(
        self,
        mod_id: str,
        element_category: str,
        identifier: str,
        display_name: str,
        workspace_json: Dict[str, Any],
        nodebox_lua_snippet: str = "",
    ) -> str:
        full_id = f"{mod_id}:{identifier}"
        safe_desc = display_name.replace('"', '\\"')
        events = workspace_json.get("events", [])

        header = [
            "-- ==========================================================================",
            "-- CODE LUA GÉNÉRÉ PAR LE COMPILATEUR BLOCKLY DE LUANTI CREATOR STUDIO",
            f"-- Élément : {display_name} ({full_id}) | Catégorie : {element_category.upper()}",
            "-- ==========================================================================",
            "",
        ]

        if element_category == "mob":
            body = self._compile_mob_entity(mod_id, identifier, full_id, events)
        elif element_category == "block":
            body = self._compile_block_node(mod_id, identifier, full_id, safe_desc, events, nodebox_lua_snippet)
        elif element_category == "item":
            body = self._compile_item_craftitem(mod_id, identifier, full_id, safe_desc, events)
        elif element_category == "command":
            body = self._compile_chatcommand(mod_id, identifier, safe_desc, events)
        else:
            body = [f'-- Élément {full_id} prêt.']

        return "\n".join(header + body) + "\n"

    def _compile_statements(self, blocks: List[Dict[str, Any]], indent_level: int = 2) -> List[str]:
        pad = "    " * indent_level
        lines: List[str] = []

        for blk in blocks:
            btype = blk.get("type", "")
            params = blk.get("params", {})
            children = blk.get("children", [])

            if btype == "cond_if_player_wields":
                item_id = params.get("item_id", "default:apple")
                lines.append(f'{pad}local wielded = player and player:get_wielded_item()')
                lines.append(f'{pad}if wielded and wielded:get_name() == "{item_id}" then')
                lines.extend(self._compile_statements(children, indent_level + 1))
                lines.append(f"{pad}end")

            elif btype == "cond_if_mob_tamed":
                lines.append(f"{pad}if self.tamed == true then")
                lines.extend(self._compile_statements(children, indent_level + 1))
                lines.append(f"{pad}end")

            elif btype == "cond_if_node_above_group":
                grp = params.get("group_name", "vegetable")
                lines.append(f"{pad}local above_pos = {{x = pos.x, y = pos.y + 1, z = pos.z}}")
                lines.append(f"{pad}local above_node = core.get_node(above_pos)")
                lines.append(f'{pad}if core.get_item_group(above_node.name, "{grp}") > 0 then')
                lines.extend(self._compile_statements(children, indent_level + 1))
                lines.append(f"{pad}end")

            elif btype == "cond_if_player_has_priv":
                priv = params.get("priv", "server")
                lines.append(f'{pad}if core.check_player_privs(player_name, {{ {priv} = true }}) then')
                lines.extend(self._compile_statements(children, indent_level + 1))
                lines.append(f"{pad}end")

            elif btype == "var_set_local":
                vname = params.get("var_name", "val")
                expr = params.get("expr", "0")
                lines.append(f"{pad}local {vname} = {expr}")

            elif btype == "stat_add_value":
                stat = params.get("stat_name", "xp")
                delta = int(params.get("delta", 10))
                lines.extend([
                    f"{pad}if player then",
                    f"{pad}    local meta = player:get_meta()",
                    f'{pad}    local cur = meta:get_int("lcs_stat_{stat}")',
                    f'{pad}    meta:set_int("lcs_stat_{stat}", cur + ({delta}))',
                    f"{pad}end",
                ])

            elif btype == "stat_check_min":
                stat = params.get("stat_name", "level")
                min_val = int(params.get("min_val", 1))
                lines.append(f'{pad}if player and player:get_meta():get_int("lcs_stat_{stat}") >= {min_val} then')
                lines.extend(self._compile_statements(children, indent_level + 1))
                lines.append(f"{pad}end")

            elif btype == "eco_add_money":
                amt = int(params.get("amount", 50))
                lines.extend([
                    f"{pad}if player then",
                    f"{pad}    local meta = player:get_meta()",
                    f'{pad}    meta:set_int("lcs_money", meta:get_int("lcs_money") + ({amt}))',
                    f"{pad}end",
                ])

            elif btype == "eco_buy_item":
                price = int(params.get("price", 50))
                item_id = params.get("item_id", "default:diamond")
                count = int(params.get("count", 1))
                lines.extend([
                    f"{pad}if player and not self._tx_lock then",
                    f"{pad}    self._tx_lock = true",
                    f"{pad}    local meta = player:get_meta()",
                    f"{pad}    local inv = player:get_inventory()",
                    f'{pad}    local balance = meta:get_int("lcs_money")',
                    f'{pad}    local stack = ItemStack("{item_id} {count}")',
                    f'{pad}    if balance >= {price} and inv:room_for_item("main", stack) then',
                    f'{pad}        meta:set_int("lcs_money", balance - {price})',
                    f'{pad}        inv:add_item("main", stack)',
                    f'{pad}        core.chat_send_player(player:get_player_name(), "Achat validé : {item_id} x{count}")',
                    f"{pad}    else",
                    f'{pad}        core.chat_send_player(player:get_player_name(), "Transaction annulée : fonds ou place insuffisants.")',
                    f"{pad}    end",
                    f"{pad}    self._tx_lock = false",
                    f"{pad}end",
                ])

            elif btype == "action_tame_mob":
                lines.extend([
                    f"{pad}self.tamed = true",
                    f"{pad}if player then",
                    f"{pad}    self.owner = player:get_player_name()",
                    f"{pad}end",
                ])

            elif btype == "action_attach_mount":
                speed = float(params.get("speed", 6.0))
                lines.extend([
                    f"{pad}if player and not self.driver then",
                    f"{pad}    self.driver = player",
                    f"{pad}    player:set_attach(self.object, \"\", {{x = 0, y = 4, z = 0}}, {{x = 0, y = 0, z = 0}})",
                    f"{pad}    self.mount_speed = {speed}",
                    f"{pad}end",
                ])

            elif btype == "action_play_animation":
                f_start = int(params.get("frame_start", 1))
                f_end = int(params.get("frame_end", 40))
                fps = int(params.get("fps", 15))
                lines.append(
                    f"{pad}self.object:set_animation({{x = {f_start}, y = {f_end}}}, {fps}, 0, true)"
                )

            elif btype == "action_spawn_particles":
                tex = params.get("texture", "heart.png")
                amount = int(params.get("amount", 12))
                lines.extend([
                    f"{pad}if pos then",
                    f"{pad}    core.add_particlespawner({{",
                    f"{pad}        amount = {amount},",
                    f"{pad}        time = 0.4,",
                    f"{pad}        minpos = {{x = pos.x - 0.4, y = pos.y + 0.2, z = pos.z - 0.4}},",
                    f"{pad}        maxpos = {{x = pos.x + 0.4, y = pos.y + 1.0, z = pos.z + 0.4}},",
                    f'{pad}        texture = "{tex}",',
                    f"{pad}    }})",
                    f"{pad}end",
                ])

            elif btype == "action_play_sound":
                snd = params.get("sound_name", "default_place_node")
                gain = float(params.get("gain", 1.0))
                lines.append(
                    f'{pad}if pos then core.sound_play("{snd}", {{pos = pos, gain = {gain}, max_hear_distance = 16}}) end'
                )

            elif btype == "action_accelerate_plant_above":
                lines.extend([
                    f"{pad}local next_stage_name = above_node.name:gsub(\"_(%d+)$\", function(n) return \"_\" .. tostring(tonumber(n) + 1) end)",
                    f"{pad}if core.registered_nodes[next_stage_name] then",
                    f"{pad}    core.swap_node(above_pos, {{name = next_stage_name, param2 = above_node.param2}})",
                    f"{pad}end",
                ])

            elif btype == "action_throw_teleport_pearl":
                vel = float(params.get("velocity", 18.0))
                consume = bool(params.get("consume", True))
                lines.extend([
                    f"{pad}if player then",
                    f"{pad}    local ppos = player:get_pos()",
                    f"{pad}    local dir = player:get_look_dir()",
                    f"{pad}    local spawn_pos = {{x = ppos.x + dir.x, y = ppos.y + 1.5 + dir.y, z = ppos.z + dir.z}}",
                    f'{pad}    local obj = core.add_entity(spawn_pos, self_pearl_entity_name)',
                    f"{pad}    if obj then",
                    f"{pad}        obj:set_velocity({{x = dir.x * {vel}, y = dir.y * {vel} + 2, z = dir.z * {vel}}})",
                    f"{pad}        obj:set_acceleration({{x = 0, y = -9.81, z = 0}})",
                    f"{pad}        obj:get_luaentity().thrower_name = player:get_player_name()",
                    f"{pad}    end",
                ])
                if consume:
                    lines.append(f"{pad}    itemstack:take_item(1)")
                lines.append(f"{pad}end")

            elif btype == "action_strike_thunder":
                lines.extend([
                    f"{pad}if pos then",
                    f"{pad}    core.add_particlespawner({{",
                    f"{pad}        amount = 40,",
                    f"{pad}        time = 0.2,",
                    f"{pad}        minpos = {{x = pos.x - 0.5, y = pos.y, z = pos.z - 0.5}},",
                    f"{pad}        maxpos = {{x = pos.x + 0.5, y = pos.y + 12, z = pos.z + 0.5}},",
                    f'{pad}        texture = "default_mese_crystal.png",',
                    f"{pad}        glow = 14,",
                    f"{pad}    }})",
                    f"{pad}end",
                ])

            elif btype == "action_open_formspec_gui":
                fname = params.get("formname", "dialogue_bdd")
                title = params.get("title", "Dialogue").replace('"', '\\"')
                text = params.get("text", "Bonjour !").replace('"', '\\"')
                lines.extend([
                    f"{pad}if player_name then",
                    f"{pad}    local fs = table.concat({{",
                    f'{pad}        "formspec_version[6]",',
                    f'{pad}        "size[9,5.5]",',
                    f'{pad}        "label[0.6,0.7;{title}]",',
                    f'{pad}        "textarea[0.6,1.3;7.8,2.5;;{text};]",',
                    f'{pad}        "button_exit[3.0,4.2;3.0,0.9;ok;Continuer]",',
                    f"{pad}    }})",
                    f'{pad}    core.show_formspec(player_name, "{fname}", fs)',
                    f"{pad}end",
                ])

            elif btype == "http_fetch_json":
                method = params.get("method", "GET")
                url = params.get("url", "https://api.example.com/status")
                lines.extend([
                    f"{pad}if _G._lcs_http_api then",
                    f"{pad}    _G._lcs_http_api.fetch({{",
                    f'{pad}        url = "{url}",',
                    f'{pad}        method = "{method}",',
                    f"{pad}        timeout = 5,",
                    f"{pad}    }}, function(res)",
                    f"{pad}        if res.succeeded and res.code == 200 then",
                    f"{pad}            local data = core.parse_json(res.data)",
                    f'{pad}            core.log("action", "[HTTP] Réponse JSON reçue avec succès.")',
                    f"{pad}        else",
                    f'{pad}            core.log("warning", "[HTTP] Échec de la requête externe.")',
                    f"{pad}        end",
                    f"{pad}    end)",
                    f"{pad}end",
                ])

        return lines

    def _compile_mob_entity(
        self, mod_id: str, identifier: str, full_id: str, events: List[Dict[str, Any]]
    ) -> List[str]:
        rightclick_stmts: List[str] = []
        for ev in events:
            if ev.get("type") == "event_mob_rightclick":
                rightclick_stmts.extend(self._compile_statements(ev.get("children", []), indent_level=2))

        lines = [
            f'core.register_entity("{full_id}", {{',
            "    initial_properties = {",
            "        hp_max = 20,",
            "        physical = true,",
            "        collide_with_objects = true,",
            "        collisionbox = {-0.35, -0.5, -0.35, 0.35, 0.5, 0.35},",
            '        visual = "mesh",',
            f'        mesh = "{mod_id}_{identifier}.glb",',
            f'        textures = {{"{mod_id}_{identifier}.png"}},',
            "    },",
            "    tamed = false,",
            "    driver = nil,",
            "    mount_speed = 4.0,",
            "    on_activate = function(self, staticdata, dtime_s)",
            "        if staticdata and staticdata ~= \"\" then",
            "            local data = core.deserialize(staticdata)",
            "            if type(data) == \"table\" then",
            "                self.tamed = data.tamed or false",
            "                self.owner = data.owner",
            "            end",
            "        end",
            "    end,",
            "    get_staticdata = function(self)",
            "        return core.serialize({tamed = self.tamed, owner = self.owner})",
            "    end,",
            "    on_rightclick = function(self, clicker)",
            "        if not clicker or not clicker:is_player() then return end",
            "        local player = clicker",
            "        local pos = self.object:get_pos()",
        ]
        lines.extend(rightclick_stmts or ["        -- Aucune logique clic droit configurée"])
        lines.extend([
            "    end,",
            "    on_step = function(self, dtime)",
            "        if self.driver and self.driver:is_player() then",
            "            local ctrl = self.driver:get_player_control()",
            "            local yaw = self.driver:get_look_horizontal()",
            "            self.object:set_yaw(yaw)",
            "            if ctrl.up then",
            "                local dir = self.driver:get_look_dir()",
            "                local v = self.object:get_velocity() or {x = 0, y = 0, z = 0}",
            "                self.object:set_velocity({x = dir.x * self.mount_speed, y = v.y, z = dir.z * self.mount_speed})",
            "            elseif ctrl.sneak then",
            "                self.driver:set_detach()",
            "                self.driver = nil",
            "            end",
            "        end",
            "    end,",
            "})",
        ])
        return lines

    def _compile_block_node(
        self,
        mod_id: str,
        identifier: str,
        full_id: str,
        safe_desc: str,
        events: List[Dict[str, Any]],
        nodebox_lua_snippet: str,
    ) -> List[str]:
        timer_interval = 0
        timer_stmts: List[str] = []

        for ev in events:
            if ev.get("type") == "event_block_timer":
                timer_interval = int(ev.get("params", {}).get("interval_sec", 5))
                timer_stmts.extend(self._compile_statements(ev.get("children", []), indent_level=2))

        lines = [
            f'core.register_node("{full_id}", {{',
            f'    description = "{safe_desc}",',
            f'    tiles = {{"{mod_id}_{identifier}.png"}},',
            "    groups = {cracky = 3, oddly_breakable_by_hand = 2},",
        ]
        if nodebox_lua_snippet.strip():
            lines.append(nodebox_lua_snippet)
        if timer_interval > 0:
            lines.extend([
                "    on_construct = function(pos)",
                f"        core.get_node_timer(pos):start({timer_interval})",
                "    end,",
                "    on_timer = function(pos, elapsed)",
            ])
            lines.extend(timer_stmts)
            lines.extend([
                "        return true",
                "    end,",
            ])
        lines.append("})")
        return lines

    def _compile_item_craftitem(
        self,
        mod_id: str,
        identifier: str,
        full_id: str,
        safe_desc: str,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        use_stmts: List[str] = []
        needs_pearl_entity = False

        for ev in events:
            if ev.get("type") == "event_item_on_use":
                for child in ev.get("children", []):
                    if child.get("type") == "action_throw_teleport_pearl":
                        needs_pearl_entity = True
                use_stmts.extend(self._compile_statements(ev.get("children", []), indent_level=2))

        lines: List[str] = []
        if needs_pearl_entity:
            pearl_ent = f"{mod_id}:{identifier}_projectile"
            lines.extend([
                f'local self_pearl_entity_name = "{pearl_ent}"',
                f'core.register_entity("{pearl_ent}", {{',
                "    initial_properties = {",
                "        physical = true,",
                "        collide_with_objects = false,",
                "        collisionbox = {-0.15, -0.15, -0.15, 0.15, 0.15, 0.15},",
                '        visual = "sprite",',
                f'        textures = {{"{mod_id}_{identifier}.png"}},',
                "    },",
                "    thrower_name = nil,",
                "    on_step = function(self, dtime, moveresult)",
                "        if moveresult and moveresult.collides then",
                "            local pos = self.object:get_pos()",
                "            if self.thrower_name then",
                "                local player = core.get_player_by_name(self.thrower_name)",
                "                if player and pos then",
                "                    local safe_dest = {x = pos.x, y = pos.y + 1.0, z = pos.z}",
                "                    local dest_node = core.get_node_or_nil(safe_dest)",
                "                    if dest_node and not core.registered_nodes[dest_node.name].walkable then",
                "                        player:set_pos(safe_dest)",
                "                    end",
                "                end",
                "            end",
                "            self.object:remove()",
                "        end",
                "    end,",
                "})",
                "",
            ])

        lines.extend([
            f'core.register_craftitem("{full_id}", {{',
            f'    description = "{safe_desc}",',
            f'    inventory_image = "{mod_id}_{identifier}.png",',
            "    on_use = function(itemstack, user, pointed_thing)",
            "        local player = user",
            "        local pos = user and user:get_pos()",
        ])
        lines.extend(use_stmts or ["        -- Logique on_use"])
        lines.extend([
            "        return itemstack",
            "    end,",
            "})",
        ])
        return lines

    def _compile_chatcommand(
        self,
        mod_id: str,
        identifier: str,
        safe_desc: str,
        events: List[Dict[str, Any]],
    ) -> List[str]:
        req_priv = ""
        cmd_stmts: List[str] = []
        for ev in events:
            if ev.get("type") == "event_command_execute":
                req_priv = ev.get("params", {}).get("required_priv", "")
                cmd_stmts.extend(self._compile_statements(ev.get("children", []), indent_level=2))

        priv_str = f"{{ {req_priv} = true }}" if req_priv else "{}"
        lines = [
            f'core.register_chatcommand("{identifier}", {{',
            '    params = "[args]",',
            f'    description = "{safe_desc}",',
            f"    privs = {priv_str},",
            "    func = function(name, param)",
            "        local player_name = name",
            "        local player = core.get_player_by_name(name)",
            "        local pos = player and player:get_pos()",
        ]
        lines.extend(cmd_stmts)
        lines.extend([
            f'        return true, "[{mod_id}] Commande /{identifier} exécutée avec succès."',
            "    end,",
            "})",
        ])
        return lines