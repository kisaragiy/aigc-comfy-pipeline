#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
workshop/creative/traditional_clothes.py — 传统服饰深挖 v1.0
==========================================================
传统服饰 = 文化符号（和服/汉服/韩服/洛丽塔——深挖第 64 轮）
用法: 传统服饰角色 → 服饰结构词（款式+层次+纹样）

【和服（日式传统）】
  振袖（正式）: 长袖+华丽纹样（"furisode, long swinging sleeves"）——成人礼/正式
  留袖（已婚）: 短袖（"tomesode"）
  浴衣（夏日祭）: 轻薄+简单纹样（"yukata, summer cotton"）——祭典标配
  访问着: 中等正式（"houmongi"）
  配件: 腰带（带缔/带扬）+木屐（"obi sash, geta sandals"）
  → 和服 = 袖长定正式度（振袖>访问着>浴衣）

【汉服（中式传统）】
  齐胸襦裙: 唐代（"hanfu, chest-high ruqun"）——华美
  曲裾: 秦汉（"quju robe"）
  褙子: 宋明（"beizi"）
  马面裙: 明代（"horse-face skirt"）
  配件: 披帛+步摇（"flowing pibo scarf, hair ornaments"）
  → 汉服 = 朝代定款式（唐襦裙/宋褙子/明马面）

【韩服（韩式传统）】
  赤古里+裙（"hanbok, jeogori and chima"）——高腰+宽裙
  特征: 高腰线+鲜艳色+短上衣（"high waist, bright colors, short jacket"）
  → 韩服 = 高腰短衣+宽裙（一眼认出）

【洛丽塔（日系洋装）】
  甜系: 粉白+蝴蝶结+蕾丝（"sweet lolita, pastel, bows, lace"）
  哥特系: 黑+十字+缎带（"gothic lolita, black, crosses, ribbons"）
  古典系: 棕茶+印花（"classic lolita, muted floral"）
  配件: 头饰+裙撑+蕾丝袜（"headpiece, petticoat, lace socks"）
  → 洛丽塔 = 三系（甜/哥特/古典——色系定系别）

【传统×场景（联动）】
  和服+祭典=夏日祭 汉服+园林=古典 韩服+宫殿=历史 洛丽塔+洋馆=幻想
  → 传统服饰 = 场景锚点（服饰+场景互相确认）

【实战映射（prompt 模板）】
  振袖: "girl in furisode kimono, long sleeves, floral pattern, formal pose"
  汉服: "girl in hanfu, chest-high ruqun, flowing pibo, traditional garden"
  韩服: "girl in hanbok, high waist, bright colors, palace background"
  甜系洛丽塔: "sweet lolita dress, pastel pink, bows, lace, tea party"
