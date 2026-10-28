using System;
using System.Collections.Generic;
using System.Globalization;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.AI;
using MonkeyNoFear.AI.Creatures;
using MonkeyNoFear.AI.Wildlife;
using MonkeyNoFear.Audio;
using MonkeyNoFear.Bunker;
using MonkeyNoFear.Core;
using MonkeyNoFear.Data;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.Items;
using MonkeyNoFear.Mining;
using MonkeyNoFear.Player;
using MonkeyNoFear.World;

namespace MonkeyNoFear.EditorTools
{
    /// <summary>
    /// Builds Scenes/MonkeyNoFear_World.unity from the level FBX files (Docs/LEVEL_MARKERS.md):
    /// geometry gets colliders/layers/surfaces; MK_* empties become props, lights, stations, ore spawn
    /// points, creatures, AI anchors, horror anchors, sounds, signs and lore; then all systems are wired,
    /// the NavMesh is baked and the scene is saved and added to the build.
    /// </summary>
    public static class LevelAssembler
    {
        class Ctx
        {
            public Transform world, systems;
            public Dictionary<string, Transform> areaRoots = new Dictionary<string, Transform>();
            public List<Transform> spawnPlayer = new List<Transform>(), spawnRespawn = new List<Transform>();
            public List<OreSpawnPoint> orePoints = new List<OreSpawnPoint>();
            public List<WildlifeSpawner.Area> wildAreas = new List<WildlifeSpawner.Area>();
            public List<Transform> fkSpawns = new List<Transform>(), fkNests = new List<Transform>(), cover = new List<Transform>();
            public List<Transform> hbSpawn = new List<Transform>(), hbPoints = new List<Transform>();
            public List<Transform> clerkSpawn = new List<Transform>();
            public Transform borerSpawn; public float borerRadius = 40f;
            public List<Transform> mournerSpawn = new List<Transform>();
            public Transform gauntSpawn; public SortedDictionary<int, Transform> gauntPath = new SortedDictionary<int, Transform>();
            public AreaZone gauntView;
            public Dictionary<string, Transform> stations = new Dictionary<string, Transform>();
            public Dictionary<string, Transform> elev = new Dictionary<string, Transform>();
            public List<Light> emergencyLights = new List<Light>();
            public List<Transform> teleports = new List<Transform>();
            public List<AreaRoot> roots = new List<AreaRoot>();
            public int markers, props, unknown;
        }

        static readonly string[] LevelFiles = { "Bunker", "Forest", "Mine" };

        public static void Build(bool bakeNavMesh = true)
        {
            KitLibrary.Refresh();
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var ctx = new Ctx();
            ctx.world = new GameObject("World").transform;
            ctx.systems = new GameObject("Systems").transform;

            foreach (var lvl in LevelFiles) ImportLevel(ctx, lvl);
            BuildSystems(ctx);
            SetupLighting(ctx);
            if (bakeNavMesh) NavMeshBaker.Bake(ctx.world);

            MNFPaths.Ensure(MNFPaths.Scenes);
            EditorSceneManager.SaveScene(scene, MNFPaths.WorldScene);
            var list = new List<EditorBuildSettingsScene> { new EditorBuildSettingsScene(MNFPaths.WorldScene, true) };
            EditorBuildSettings.scenes = list.ToArray();
            Debug.Log($"[MNF] World assembled: {ctx.markers} markers, {ctx.props} props, {ctx.unknown} unknown markers.");
        }

        // ------------------------------------------------------------------ levels
        static void ImportLevel(Ctx ctx, string level)
        {
            var path = $"{MNFPaths.Levels}/{level}.fbx";
            var asset = AssetDatabase.LoadAssetAtPath<GameObject>(path);
            if (!asset) { Debug.LogError($"[MNF] Level {path} missing — run Tools/blender/levels/build_levels.py"); return; }
            var root = new GameObject("Area_" + level).transform;
            root.SetParent(ctx.world, false);
            ctx.areaRoots[level] = root;
            var inst = (GameObject)PrefabUtility.InstantiatePrefab(asset);
            PrefabUtility.UnpackPrefabInstance(inst, PrefabUnpackMode.Completely, InteractionMode.AutomatedAction);
            inst.transform.SetParent(root, false);
            inst.name = level + "_Geometry";

            var ar = root.gameObject.AddComponent<AreaRoot>();
            switch (level)
            {
                case "Bunker": ar.area = AreaId.Bunker; ar.alsoActiveIn = new[] { AreaId.Corridor, AreaId.Forest }; break;
                case "Forest": ar.area = AreaId.Forest; ar.alsoActiveIn = new[] { AreaId.Corridor, AreaId.MineShallow }; break;
                default: ar.area = AreaId.MineShallow; ar.alsoActiveIn = new[] { AreaId.Forest, AreaId.MineMid, AreaId.MineDeep }; break;
            }
            ctx.roots.Add(ar);

            var all = inst.GetComponentsInChildren<Transform>(true);
            foreach (var t in all)
            {
                if (!t || t == inst.transform) continue;
                var name = CleanName(t.name);
                if (name.StartsWith("MK_")) { ctx.markers++; try { Marker(ctx, root, t, name); } catch (Exception e) { Debug.LogError($"[MNF] Marker {t.name}: {e.Message}\n{e.StackTrace}"); } }
                else Geometry(ctx, t, name, level);
            }
            // markers have been converted; remove the empties
            foreach (var t in all) if (t && CleanName(t.name).StartsWith("MK_")) UnityEngine.Object.DestroyImmediate(t.gameObject);
        }

        static string CleanName(string n)
        {
            int dot = n.LastIndexOf('.');
            if (dot > 0 && dot < n.Length - 1 && char.IsDigit(n[dot + 1])) n = n.Substring(0, dot);
            return n;
        }

        static void Geometry(Ctx ctx, Transform t, string name, string level)
        {
            var mf = t.GetComponent<MeshFilter>();
            var mr = t.GetComponent<MeshRenderer>();
            if (!mf || !mf.sharedMesh) return;
            if (name.StartsWith("ZONE_"))
            {
                var parts = name.Split('_');
                if (Enum.TryParse(parts[1], out AreaId area))
                {
                    var z = MakeBoxFromMesh(t, "Zone_" + area);
                    var az = z.AddComponent<AreaZone>(); az.area = area; az.priority = parts.Length > 2 ? Int(parts[2], 0) : 0;
                }
                UnityEngine.Object.DestroyImmediate(t.gameObject);
                return;
            }
            if (name.StartsWith("KILL_")) { MakeBoxFromMesh(t, "Kill").AddComponent<KillVolume>(); UnityEngine.Object.DestroyImmediate(t.gameObject); return; }
            if (name.StartsWith("GAUNTVIEW"))
            {
                var z = MakeBoxFromMesh(t, "GauntView");
                var az = z.AddComponent<AreaZone>(); az.area = AreaId.MineDeep; az.priority = -100;
                ctx.gauntView = az;
                UnityEngine.Object.DestroyImmediate(t.gameObject);
                return;
            }
            bool noCol = name.StartsWith("NOCOL_") || name.StartsWith("WATER_");
            bool colOnly = name.StartsWith("COLONLY_");
            bool noClimb = name.StartsWith("NOCLIMB_");
            if (name.StartsWith("WATER_") && mr) mr.sharedMaterial = MaterialFactory.Get("MNF_Water");
            if (!noCol)
            {
                var mc = t.gameObject.AddComponent<MeshCollider>();
                mc.sharedMesh = mf.sharedMesh;
                var s = t.gameObject.AddComponent<Surface>();
                s.kind = mr && mr.sharedMaterial ? Surface.FromName(mr.sharedMaterial.name) : SurfaceKind.Rock;
                if (noClimb) s.slipperiness = 1f;
            }
            if (colOnly && mr) mr.enabled = false;
            t.gameObject.layer = noClimb ? Layers.NoClimb : Layers.Environment;
            if (mr)
            {
                mr.shadowCastingMode = level == "Forest" ? UnityEngine.Rendering.ShadowCastingMode.On : UnityEngine.Rendering.ShadowCastingMode.TwoSided;
                mr.receiveShadows = true;
            }
            if (name.StartsWith("UNSTABLE_"))
            {
                var u = t.gameObject.AddComponent<UnstableFloor>();
                u.sensorSize = mf.sharedMesh.bounds.size + Vector3.up;
                u.floorObject = t.gameObject;
                return; // moves: not static
            }
            PrefabFactory.SetStatic(t.gameObject, true);
            GameObjectUtility.SetStaticEditorFlags(t.gameObject, GameObjectUtility.GetStaticEditorFlags(t.gameObject) | StaticEditorFlags.ContributeGI);
        }

        static GameObject MakeBoxFromMesh(Transform t, string name)
        {
            var b = t.GetComponent<Renderer>().bounds;
            var go = new GameObject(name);
            go.transform.SetParent(t.parent, false);
            go.transform.position = b.center;
            var bc = go.AddComponent<BoxCollider>();
            bc.size = b.size; bc.isTrigger = true;
            go.layer = Layers.Trigger;
            return go;
        }

        static float F(string s, float d) => float.TryParse(s, NumberStyles.Float, CultureInfo.InvariantCulture, out var v) ? v : d;
        static int Int(string s, int d) => int.TryParse(s, out var v) ? v : d;

        static GameObject Place(GameObject prefab, Transform at, Transform parent, string name = null)
        {
            if (!prefab) return null;
            var go = (GameObject)PrefabUtility.InstantiatePrefab(prefab, parent);
            go.transform.SetPositionAndRotation(at.position, at.rotation);
            float s = at.lossyScale.x;
            if (Mathf.Abs(s - 1f) > 0.01f && s > 0.05f) go.transform.localScale = Vector3.one * s;
            if (name != null) go.name = name;
            return go;
        }

        static Transform Anchor(Transform at, Transform parent, string name)
        {
            var t = new GameObject(name).transform;
            t.SetParent(parent, false);
            t.SetPositionAndRotation(at.position, at.rotation);
            return t;
        }

        // ------------------------------------------------------------------ markers
        static void Marker(Ctx ctx, Transform root, Transform m, string name)
        {
            var p = name.Split('_');
            string type = p.Length > 1 ? p[1] : "";
            string a1 = p.Length > 2 ? p[2] : "";
            switch (type)
            {
                case "SPAWN":
                    var sp = Anchor(m, root, "Spawn_" + a1);
                    if (a1 == "Player") ctx.spawnPlayer.Add(sp); else ctx.spawnRespawn.Add(sp);
                    ctx.teleports.Add(sp);
                    break;
                case "PROP":
                {
                    string pname = name.Substring("MK_PROP_".Length);
                    var prefab = PrefabFactory.Prop(pname) ?? PrefabFactory.Load(PrefabFactory.ItemsDir, "Item_" + pname);
                    if (!prefab) { ctx.unknown++; Debug.LogWarning("[MNF] No prop prefab for " + pname); break; }
                    Place(prefab, m, root); ctx.props++;
                    break;
                }
                case "LIGHT": LightPreset(ctx, root, m, a1); break;
                case "ORE":
                {
                    var go = Anchor(m, root, name).gameObject;
                    var op = go.AddComponent<OreSpawnPoint>();
                    op.zone = a1 == "Mid" ? DepthZone.Mid : a1 == "Deep" ? DepthZone.Deep : a1 == "Anomalous" ? DepthZone.Anomalous : DepthZone.Shallow;
                    op.wallMounted = name.EndsWith("_Wall");
                    op.activeChance = op.zone == DepthZone.Anomalous ? 0.8f : 0.65f;
                    ctx.orePoints.Add(op);
                    break;
                }
                case "WILD":
                {
                    var c = Anchor(m, root, name);
                    var prefab = PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_" + a1);
                    ctx.wildAreas.Add(new WildlifeSpawner.Area { centre = c, prefab = prefab, count = p.Length > 3 ? Int(p[3], 3) : 3, radius = p.Length > 4 ? F(p[4], 12f) : 12f, falsekinAllowed = name.EndsWith("_FK") });
                    break;
                }
                case "FALSEKIN": ctx.fkSpawns.Add(Anchor(m, root, name)); break;
                case "FKNEST": ctx.fkNests.Add(Anchor(m, root, name)); Place(PrefabFactory.Prop("Nest"), m, root); break;
                case "COVER": ctx.cover.Add(Anchor(m, root, name)); break;
                case "HB": if (a1 == "SPAWN") ctx.hbSpawn.Add(Anchor(m, root, name)); else ctx.hbPoints.Add(Anchor(m, root, name)); break;
                case "CLERK":
                    if (a1 == "SPAWN") ctx.clerkSpawn.Add(Anchor(m, root, name));
                    else Anchor(m, root, name).gameObject.AddComponent<ClerkNode>();
                    break;
                case "BORER":
                    if (a1 == "SPAWN") { ctx.borerSpawn = Anchor(m, root, name); ctx.borerRadius = p.Length > 3 ? F(p[3], 40f) : 40f; }
                    else
                    {
                        var hole = Anchor(m, root, name).gameObject.AddComponent<BorerHole>();
                        if (name.EndsWith("_Plug"))
                        {
                            var plug = Place(PrefabFactory.Prop("LooseRockWall"), m, hole.transform);
                            hole.plug = plug;
                        }
                        else Place(PrefabFactory.Prop("BorerHole"), m, hole.transform);
                    }
                    break;
                case "MOURNER":
                    if (a1 == "SPAWN") ctx.mournerSpawn.Add(Anchor(m, root, name));
                    else Anchor(m, root, name).gameObject.AddComponent<MournerPoint>().isLure = a1 == "LURE";
                    break;
                case "GAUNT":
                    if (a1 == "SPAWN") ctx.gauntSpawn = Anchor(m, root, name);
                    else ctx.gauntPath[p.Length > 3 ? Int(p[3], ctx.gauntPath.Count) : ctx.gauntPath.Count] = Anchor(m, root, name);
                    break;
                case "EVENT": EventAnchor(ctx, root, m, name.Substring("MK_EVENT_".Length)); break;
                case "SOUND":
                {
                    var e = Anchor(m, root, name).gameObject.AddComponent<AmbientEmitter>();
                    string snd = name.Substring("MK_SOUND_".Length);
                    if (snd.EndsWith("_loop")) e.loop = snd; else { e.oneShot = snd; e.interval = new Vector2(3f, 11f); }
                    break;
                }
                case "SIGN": Quad(root, m, "MNF_Signs", Int(a1, 0), p.Length > 3 ? F(p[3], 0.6f) : 0.6f, p.Length > 4 ? F(p[4], 0.6f) : 0.6f, "Sign"); break;
                case "DECAL": { float s = p.Length > 3 ? F(p[3], 0.8f) : 0.8f; Quad(root, m, "MNF_Decals", Int(a1, 0), s, s, "Decal"); break; }
                case "LORE":
                {
                    bool tape = name.EndsWith("_Tape");
                    string id = name.Substring("MK_LORE_".Length).Replace("_Tape", "");
                    var go = Place(PrefabFactory.Load(PrefabFactory.ItemsDir, tape ? "Item_LoreTape" : "Item_LoreNote"), m, root);
                    if (go) go.GetComponent<LoreItem>().loreId = id;
                    break;
                }
                case "ITEM":
                {
                    var def = AssetDatabase.LoadAssetAtPath<ItemDefinition>($"{DataFactory.Items}/Item_{name.Substring("MK_ITEM_".Length)}.asset");
                    if (def && def.prefab) Place(def.prefab, m, root); else ctx.unknown++;
                    break;
                }
                case "STATION": Station(ctx, root, m, a1); break;
                case "ELEV": ctx.elev[a1] = Anchor(m, root, name); break;
                case "ROPE":
                {
                    float len = F(a1, 8f);
                    var top = m.position;
                    var r = DeployedRopeStatic(root, top, top + Vector3.down * len);
                    break;
                }
                case "FOGBANK": FogBank(root, m); break;
                case "TELEPORT": ctx.teleports.Add(Anchor(m, root, name)); break;
                default: ctx.unknown++; Debug.LogWarning("[MNF] Unknown marker " + name); break;
            }
        }

        static GameObject DeployedRopeStatic(Transform parent, Vector3 top, Vector3 bottom)
        {
            var go = new GameObject("FixedRope");
            go.transform.SetParent(parent, false);
            go.transform.position = (top + bottom) * 0.5f;
            var vis = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            UnityEngine.Object.DestroyImmediate(vis.GetComponent<Collider>());
            vis.transform.SetParent(go.transform, false);
            float len = Vector3.Distance(top, bottom);
            vis.transform.localScale = new Vector3(0.04f, len * 0.5f, 0.04f);
            vis.GetComponent<Renderer>().sharedMaterial = MaterialFactory.Get("MNF_Rope");
            var col = go.AddComponent<CapsuleCollider>(); col.direction = 1; col.radius = 0.06f; col.height = len;
            go.AddComponent<Surface>().kind = SurfaceKind.Wood;
            go.layer = Layers.Environment;
            return go;
        }

        static void Quad(Transform parent, Transform m, string mat, int cell, float w, float h, string name)
        {
            var go = new GameObject($"{name}_{cell}");
            go.transform.SetParent(parent, false);
            go.transform.SetPositionAndRotation(m.position + m.forward * 0.01f, m.rotation);
            go.AddComponent<MeshFilter>().sharedMesh = PrefabFactory.AtlasQuad(cell, w, h);
            var r = go.AddComponent<MeshRenderer>();
            r.sharedMaterial = MaterialFactory.Get(mat);
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            PrefabFactory.SetStatic(go, true);
        }

        static void FogBank(Transform parent, Transform m)
        {
            var go = new GameObject("FogBank");
            go.transform.SetParent(parent, false);
            go.transform.position = m.position;
            var ps = go.AddComponent<ParticleSystem>();
            var main = ps.main;
            main.loop = true; main.prewarm = true; main.startLifetime = 40f; main.startSpeed = 0.05f;
            main.startSize = new ParticleSystem.MinMaxCurve(12f, 22f); main.maxParticles = 12;
            main.startColor = new Color(0.55f, 0.6f, 0.65f, 0.22f); main.simulationSpace = ParticleSystemSimulationSpace.World;
            var em = ps.emission; em.rateOverTime = 0.3f;
            var sh = ps.shape; sh.shapeType = ParticleSystemShapeType.Box; sh.scale = new Vector3(30f, 3f, 30f);
            var r = go.GetComponent<ParticleSystemRenderer>();
            r.sharedMaterial = MaterialFactory.Get("MNF_FX_Fog");
            r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
        }

        // ------------------------------------------------------------------ lights
        static void LightPreset(Ctx ctx, Transform root, Transform m, string preset)
        {
            GameObject fixture = null; Light l = null;
            Vector3 down = Vector3.down * 0.25f;
            switch (preset)
            {
                case "Fluor":
                case "FluorBad":
                    fixture = Place(PrefabFactory.Prop("FluorescentFixture"), m, root);
                    l = PrefabFactory.AddLight(fixture ? fixture.transform : root, "Light", LightType.Point, new Color(0.82f, 0.9f, 1f), 9f, preset == "Fluor" ? 1.3f : 0.9f, fixture ? down : m.position);
                    var fl = l.gameObject.AddComponent<FlickerLight>();
                    fl.emissive = fixture ? KitLibrary.FindDeep(fixture.transform, "Tube")?.GetComponent<Renderer>() : null;
                    fl.stuttersPerMinute = preset == "Fluor" ? 1.2f : 14f;
                    if (UnityEngine.Random.value < 0.35f) fl.humLoop = "fluorescent_hum_loop";
                    break;
                case "Cage":
                    fixture = Place(PrefabFactory.Prop("CageLamp"), m, root);
                    l = PrefabFactory.AddLight(fixture ? fixture.transform : root, "Light", LightType.Point, new Color(1f, 0.75f, 0.45f), 6f, 1f, fixture ? Vector3.forward * 0.15f : m.position);
                    l.gameObject.AddComponent<FlickerLight>().stuttersPerMinute = 0.6f;
                    break;
                case "Emergency":
                    fixture = Place(PrefabFactory.Prop("EmergencyLight"), m, root);
                    l = PrefabFactory.AddLight(fixture ? fixture.transform : root, "Light", LightType.Point, new Color(1f, 0.08f, 0.05f), 8f, 1.5f, fixture ? Vector3.forward * 0.12f : m.position);
                    ctx.emergencyLights.Add(l);
                    break;
                case "Red":
                    fixture = Place(PrefabFactory.Prop("EmergencyLight"), m, root);
                    l = PrefabFactory.AddLight(fixture ? fixture.transform : root, "Light", LightType.Point, new Color(1f, 0.1f, 0.06f), 6f, 0.6f, fixture ? Vector3.forward * 0.12f : m.position);
                    break;
                case "MineLamp":
                case "MineLampDim":
                    fixture = Place(PrefabFactory.Prop("MineLamp"), m, root);
                    l = PrefabFactory.AddLight(fixture ? fixture.transform : root, "Light", LightType.Point, new Color(1f, 0.68f, 0.38f), preset == "MineLamp" ? 7.5f : 5f, preset == "MineLamp" ? 1.0f : 0.55f, fixture ? Vector3.forward * 0.18f : m.position);
                    var mf = l.gameObject.AddComponent<FlickerLight>(); mf.followsBunkerPower = false; mf.stuttersPerMinute = 1.5f; mf.flickerSound = false;
                    mf.emissive = fixture ? KitLibrary.FindDeep(fixture.transform, "Bulb")?.GetComponent<Renderer>() : null;
                    break;
                case "String":
                    fixture = Place(PrefabFactory.Prop("LampString"), m, root);
                    for (int i = 0; i < 2; i++)
                        PrefabFactory.AddLight(fixture ? fixture.transform : root, "Light" + i, LightType.Point, new Color(1f, 0.7f, 0.4f), 6f, 0.7f, new Vector3(-1f + i * 2f, -0.3f, 0f));
                    break;
                case "Crystal":
                    l = PrefabFactory.AddLight(root, "CrystalGlow", LightType.Point, new Color(0.4f, 0.85f, 1f), 6f, 0.6f, Vector3.zero);
                    l.transform.position = m.position;
                    break;
                case "Camp":
                    Place(PrefabFactory.Prop("CampLantern"), m, root);
                    break;
                case "Spot":
                    l = PrefabFactory.AddLight(root, "Spot", LightType.Spot, new Color(1f, 0.85f, 0.65f), 12f, 1.6f, Vector3.zero);
                    l.transform.SetPositionAndRotation(m.position, m.rotation);
                    l.spotAngle = 70f;
                    break;
                default:
                    Debug.LogWarning("[MNF] Unknown light preset " + preset);
                    break;
            }
            if (l && preset != "Spot" && !fixture) l.transform.position = m.position;
        }

        // ------------------------------------------------------------------ horror anchors
        static void EventAnchor(Ctx ctx, Transform root, Transform m, string type)
        {
            if (!Enum.TryParse(type, out HorrorEventType t)) { ctx.unknown++; Debug.LogWarning("[MNF] Unknown event " + type); return; }
            var a = Anchor(m, root, "Horror_" + type).gameObject.AddComponent<HorrorAnchor>();
            a.type = t;
            switch (t)
            {
                case HorrorEventType.MinecartNudge:
                    var cart = Place(PrefabFactory.Prop("Minecart"), m, a.transform);
                    if (cart) { PrefabFactory.SetStatic(cart, false); cart.AddComponent<MinecartEvent>(); a.target = cart; }
                    a.oncePerExpedition = false;
                    break;
                case HorrorEventType.WallScratch:
                    Place(PrefabFactory.Prop("ScratchedPlate"), m, a.transform);
                    var decal = new GameObject("FreshScratches");
                    decal.transform.SetParent(a.transform, false);
                    decal.transform.localPosition = Vector3.forward * 0.06f + Vector3.up * 1.2f;
                    decal.AddComponent<MeshFilter>().sharedMesh = PrefabFactory.AtlasQuad(5, 1.1f, 1.1f);
                    decal.AddComponent<MeshRenderer>().sharedMaterial = MaterialFactory.Get("MNF_Decals");
                    decal.SetActive(false);
                    a.reveal = new[] { decal };
                    a.oncePerExpedition = true;
                    break;
                case HorrorEventType.LightTurnsOn:
                    var lamp = Place(PrefabFactory.Prop("MineLamp"), m, a.transform);
                    var l = PrefabFactory.AddLight(lamp ? lamp.transform : a.transform, "DeadLamp", LightType.Point, new Color(1f, 0.7f, 0.4f), 9f, 1.2f, Vector3.forward * 0.18f);
                    l.enabled = false;
                    a.lightTarget = l;
                    break;
                case HorrorEventType.PARecording:
                    Place(PrefabFactory.Prop("PA_Speaker"), m, a.transform);
                    a.requireUnseen = false; a.maxDistance = 40f;
                    break;
                case HorrorEventType.PeripheralSilhouette:
                    bool mine = m.position.y < -2f || root.name.Contains("Mine");
                    var sil = Place(PrefabFactory.Load(PrefabFactory.CreaturesDir, mine ? "Silhouette_LanternMourner" : "Silhouette_Hollowback"), m, a.transform);
                    if (sil) { sil.SetActive(false); a.target = sil; }
                    a.requireUnseen = false; a.minDistance = 14f; a.maxDistance = 40f;
                    break;
                case HorrorEventType.RadioInterference:
                case HorrorEventType.PipeKnock:
                    a.requireUnseen = false; a.minDistance = 0f; a.maxDistance = 25f;
                    break;
            }
        }

        // ------------------------------------------------------------------ stations
        static void Station(Ctx ctx, Transform root, Transform m, string name)
        {
            GameObject prefab = null;
            switch (name)
            {
                case "Terminal": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_Terminal"); break;
                case "SellMachine": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_SellMachine"); break;
                case "StorageLocker": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_StorageLocker"); break;
                case "ToolRack": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_ToolRack"); break;
                case "Dispenser": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_Dispenser"); break;
                case "Bed": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_Bed"); break;
                case "Gate": prefab = PrefabFactory.Load(PrefabFactory.StationsDir, "Station_Gate"); break;
                case "Generator": prefab = PrefabFactory.Prop("Generator"); break;
                case "Radio": prefab = PrefabFactory.Prop("Radio"); break;
                case "Workbench": prefab = PrefabFactory.Prop("Workbench"); break;
            }
            if (!prefab) { Debug.LogWarning("[MNF] Station prefab missing: " + name); ctx.unknown++; return; }
            var go = Place(prefab, m, root, "Station_" + name);
            ctx.stations[name] = go.transform;
            if (name == "Radio")
            {
                var a = go.AddComponent<HorrorAnchor>(); a.type = HorrorEventType.RadioInterference; a.requireUnseen = false; a.minDistance = 0f; a.maxDistance = 30f;
                go.AddComponent<AmbientEmitter>().loop = "radio_static_loop";
            }
            if (name == "Generator") go.AddComponent<AmbientEmitter>().loop = "generator_loop";
            if (name == "Gate" || name == "Bed" || name == "Terminal" || name == "SellMachine" || name == "Dispenser") PrefabFactory.SetStatic(go, false);
        }

        // ------------------------------------------------------------------ systems
        static void BuildSystems(Ctx ctx)
        {
            var sys = ctx.systems;
            var rootGo = new GameObject("GameRoot");
            rootGo.transform.SetParent(sys, false);
            var gr = rootGo.AddComponent<GameRoot>();
            gr.itemDatabase = AssetDatabase.LoadAssetAtPath<ItemDatabase>(MNFPaths.Data + "/ItemDatabase.asset");
            gr.shopCatalog = AssetDatabase.LoadAssetAtPath<ShopCatalog>(MNFPaths.Data + "/ShopCatalog.asset");
            gr.loreDatabase = AssetDatabase.LoadAssetAtPath<LoreDatabase>(MNFPaths.Data + "/LoreDatabase.asset");
            gr.lostPackPrefab = PrefabFactory.Load(PrefabFactory.ItemsDir, "Item_Backpack");

            var audio = rootGo.AddComponent<AudioManager>();
            audio.bank = AssetDatabase.LoadAssetAtPath<SoundBank>(AudioFactory.BankPath);

            var area = rootGo.AddComponent<AreaManager>();
            foreach (AreaId id in Enum.GetValues(typeof(AreaId)))
            {
                var prof = DataFactory.Atmosphere(id);
                if (prof) area.profiles.Add(prof);
            }
            area.roots = ctx.roots;
            area.startArea = AreaId.Bunker;

            rootGo.AddComponent<ExpeditionManager>();
            var amb = rootGo.AddComponent<AmbienceController>();
            var dir = rootGo.AddComponent<HorrorEventDirector>();
            dir.ambience = amb;
            dir.events = DefaultHorrorEvents();

            var res = rootGo.AddComponent<ResourceDistributor>();
            foreach (var m in AssetDatabase.FindAssets("t:MineralDefinition", new[] { DataFactory.Minerals }))
                res.minerals.Add(AssetDatabase.LoadAssetAtPath<MineralDefinition>(AssetDatabase.GUIDToAssetPath(m)));
            res.points = ctx.orePoints;

            var debug = rootGo.AddComponent<DebugOverlay>();
            debug.teleportTargets = ctx.teleports.ToArray();

            var navGo = new GameObject("NavMesh");
            navGo.transform.SetParent(sys, false);
            navGo.AddComponent<NavMeshDataLoader>();

            // FX + player
            var fxPrefab = PrefabFactory.Load(PrefabFactory.SystemDir, "FX");
            if (fxPrefab) PrefabUtility.InstantiatePrefab(fxPrefab, sys);
            var playerPrefab = PrefabFactory.Load(PrefabFactory.SystemDir, "PlayerRig");
            var spawn = ctx.spawnPlayer.Count > 0 ? ctx.spawnPlayer[0] : null;
            if (playerPrefab)
            {
                var player = (GameObject)PrefabUtility.InstantiatePrefab(playerPrefab, sys);
                if (spawn) player.transform.SetPositionAndRotation(spawn.position, Quaternion.Euler(0f, spawn.eulerAngles.y, 0f));
                var hp = player.GetComponent<PlayerHealth>();
                hp.respawnPoint = ctx.spawnRespawn.Count > 0 ? ctx.spawnRespawn[0] : spawn;
            }
            else Debug.LogError("[MNF] PlayerRig prefab missing");

            WireBunker(ctx);
            SpawnCreatures(ctx);
            WireElevator(ctx);
        }

        static List<HorrorEventDirector.EventDef> DefaultHorrorEvents()
        {
            var mine = new[] { AreaId.MineShallow, AreaId.MineMid, AreaId.MineDeep };
            var forest = new[] { AreaId.Forest };
            var bunker = new[] { AreaId.Bunker, AreaId.Corridor };
            HorrorEventDirector.EventDef E(HorrorEventType t, float w, AreaId[] a, float cd, int depth = 0) => new HorrorEventDirector.EventDef { type = t, weight = w, areas = a, cooldown = cd, minDepth = depth };
            return new List<HorrorEventDirector.EventDef>
            {
                E(HorrorEventType.PhantomFootsteps, 3, mine, 90), E(HorrorEventType.RockFall, 3, mine, 60), E(HorrorEventType.MinecartNudge, 1.5f, mine, 240),
                E(HorrorEventType.WallScratch, 1.5f, mine, 300, 2), E(HorrorEventType.LightTurnsOn, 1.5f, mine, 240), E(HorrorEventType.DeadRoomHum, 1, mine, 300),
                E(HorrorEventType.MetalRepeat, 1.5f, mine, 200, 2), E(HorrorEventType.PARecording, 1, mine, 400), E(HorrorEventType.PeripheralSilhouette, 1, mine, 420, 2),
                E(HorrorEventType.Whisper, 0.7f, mine, 300, 3),
                E(HorrorEventType.DistantCallStops, 3, forest, 120), E(HorrorEventType.BranchSnap, 3, forest, 60), E(HorrorEventType.TreeCreak, 2, forest, 60),
                E(HorrorEventType.FoliageCircling, 1.2f, forest, 300), E(HorrorEventType.Crow, 1.5f, forest, 120), E(HorrorEventType.PeripheralSilhouette, 0.8f, forest, 500),
                E(HorrorEventType.BunkerImpact, 2, bunker, 180), E(HorrorEventType.BunkerCreak, 2, bunker, 90), E(HorrorEventType.RadioInterference, 1.5f, bunker, 150),
                E(HorrorEventType.PipeKnock, 1.5f, bunker, 120), E(HorrorEventType.LightFlicker, 1.5f, bunker, 120), E(HorrorEventType.PowerDip, 0.6f, bunker, 600),
            };
        }

        static void WireBunker(Ctx ctx)
        {
            Transform t;
            SecurityGate gate = ctx.stations.TryGetValue("Gate", out t) ? t.GetComponent<SecurityGate>() : null;
            var gen = ctx.stations.TryGetValue("Generator", out t) ? t : null;
            var powerGo = new GameObject("BunkerPower");
            powerGo.transform.SetParent(ctx.systems, false);
            var power = powerGo.AddComponent<BunkerPower>();
            power.gate = gate; power.generator = gen; power.emergencyLights = ctx.emergencyLights.ToArray();
            if (ctx.stations.TryGetValue("Terminal", out t) && ctx.stations.TryGetValue("SellMachine", out var s))
                t.GetComponent<BunkerTerminal>().sellStation = s.GetComponent<SellStation>();
            foreach (var key in new[] { "Terminal", "SellMachine", "StorageLocker", "ToolRack", "Dispenser", "Bed", "Gate" })
                if (!ctx.stations.ContainsKey(key)) Debug.LogWarning("[MNF] Bunker is missing station marker MK_STATION_" + key);
        }

        static void SpawnCreatures(Ctx ctx)
        {
            var parent = new GameObject("Creatures").transform;
            parent.SetParent(ctx.world, false);

            // wildlife + falsekin
            var wildGo = new GameObject("Wildlife");
            wildGo.transform.SetParent(ctx.areaRoots.TryGetValue("Forest", out var fr) ? fr : parent, false);
            var spawner = wildGo.AddComponent<WildlifeSpawner>();
            spawner.areas = ctx.wildAreas;
            var fkPrefab = PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_Falsekin");
            foreach (var s in ctx.fkSpawns)
            {
                var go = Place(fkPrefab, s, wildGo.transform);
                if (!go) continue;
                var fk = go.GetComponent<Falsekin>();
                fk.coverPoints = ctx.cover;
                foreach (var a in ctx.wildAreas) if (a.falsekinAllowed) fk.redisguisePoints.Add(a.centre);
                fk.nest = Nearest(ctx.fkNests, s.position);
                spawner.falsekin.Add(fk);
            }
            spawner.falsekinPerExpedition = Mathf.Max(1, ctx.fkSpawns.Count / 2 + 1);

            var forestRoot = ctx.areaRoots.TryGetValue("Forest", out var f) ? f : parent;
            var mineRoot = ctx.areaRoots.TryGetValue("Mine", out var mr) ? mr : parent;
            foreach (var s in ctx.hbSpawn)
            {
                var go = Place(PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_Hollowback"), s, forestRoot);
                if (go) go.GetComponent<Hollowback>().interestPoints = ctx.hbPoints;
            }
            foreach (var s in ctx.clerkSpawn) Place(PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_CeilingClerk"), s, mineRoot);
            if (ctx.borerSpawn)
            {
                var go = Place(PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_Borer"), ctx.borerSpawn, mineRoot);
                if (go) { var b = go.GetComponent<Borer>(); b.territoryCentre = ctx.borerSpawn; b.territoryRadius = ctx.borerRadius; }
            }
            foreach (var s in ctx.mournerSpawn) Place(PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_LanternMourner"), s, mineRoot);
            if (ctx.gauntSpawn)
            {
                var go = Place(PrefabFactory.Load(PrefabFactory.CreaturesDir, "Creature_Gaunt"), ctx.gauntSpawn, mineRoot);
                if (go)
                {
                    var g = go.GetComponent<Gaunt>();
                    g.path = new List<Transform>(ctx.gauntPath.Values);
                    g.viewZone = ctx.gauntView;
                }
            }
        }

        static Transform Nearest(List<Transform> list, Vector3 p)
        {
            Transform best = null; float bd = float.MaxValue;
            foreach (var t in list) { float d = (t.position - p).sqrMagnitude; if (d < bd) { bd = d; best = t; } }
            return best;
        }

        static void WireElevator(Ctx ctx)
        {
            if (!ctx.elev.TryGetValue("Top", out var top) || !ctx.elev.TryGetValue("Bottom", out var bottom)) return;
            var go = new GameObject("ServiceElevator");
            go.transform.SetParent(ctx.areaRoots.TryGetValue("Mine", out var mr) ? mr : ctx.world, false);
            go.transform.position = top.position;
            var el = go.AddComponent<ServiceElevator>();
            el.topStop = top; el.bottomStop = bottom;
            var plat = Place(PrefabFactory.Load(PrefabFactory.StationsDir, "Station_ElevatorPlatform"), top, go.transform);
            if (plat) { PrefabFactory.SetStatic(plat, false); el.platform = plat.transform; }
            // controls: a button on the platform, call buttons at each stop, breaker lever at the bottom
            if (plat) PrefabFactory.MakeButton(plat.transform, "Btn_Go", new Vector3(1.3f, 1.1f, 1.3f), Vector3.up, "BigButton_Body", "BigButton_Cap", el, "go", "LIFT", 0.06f);
            if (ctx.elev.TryGetValue("CallTop", out var ct)) PrefabFactory.MakeButton(go.transform, "Btn_CallTop", go.transform.InverseTransformPoint(ct.position), go.transform.InverseTransformDirection(ct.forward), "BigButton_Body", "BigButton_Cap", el, "call_top", "CALL", 0.06f, true);
            if (ctx.elev.TryGetValue("CallBottom", out var cb)) PrefabFactory.MakeButton(go.transform, "Btn_CallBottom", go.transform.InverseTransformPoint(cb.position), go.transform.InverseTransformDirection(cb.forward), "BigButton_Body", "BigButton_Cap", el, "call_bottom", "CALL", 0.06f, true);
            if (ctx.elev.TryGetValue("Breaker", out var br))
            {
                PrefabFactory.MakeLever(go.transform, go.transform.InverseTransformPoint(br.position), go.transform.InverseTransformDirection(br.forward), el, "breaker", "", "LIFT\nBREAKER");
                el.breakerLamp = PrefabFactory.AddLight(go.transform, "BreakerLamp", LightType.Point, new Color(1f, 0.15f, 0.1f), 4f, 1f, go.transform.InverseTransformPoint(br.position + br.forward * 0.3f + Vector3.up * 0.4f));
            }
        }

        // ------------------------------------------------------------------ lighting
        static void SetupLighting(Ctx ctx)
        {
            var moonGo = new GameObject("Moon");
            moonGo.transform.SetParent(ctx.systems, false);
            moonGo.transform.rotation = Quaternion.Euler(38f, 205f, 0f);
            var moon = moonGo.AddComponent<Light>();
            moon.type = LightType.Directional;
            moon.color = new Color(0.55f, 0.63f, 0.82f);
            moon.intensity = 0.35f;
            moon.shadows = LightShadows.Soft;
            moon.shadowStrength = 0.75f;
            var area = UnityEngine.Object.FindObjectOfType<AreaManager>();
            if (area) area.moonLight = moon;

            RenderSettings.skybox = null;
            RenderSettings.ambientMode = UnityEngine.Rendering.AmbientMode.Trilight;
            RenderSettings.fog = true;
            RenderSettings.fogMode = FogMode.ExponentialSquared;
            RenderSettings.fogColor = new Color(0.05f, 0.05f, 0.055f);
            RenderSettings.fogDensity = 0.012f;
            RenderSettings.sun = moon;
            // realtime lighting only: no lightmap bakes are triggered by opening the scene
            MNFPaths.Ensure(MNFPaths.Generated);
            var lsPath = MNFPaths.Generated + "/WorldLighting.lighting";
            var ls = AssetDatabase.LoadAssetAtPath<LightingSettings>(lsPath);
            if (!ls) { ls = new LightingSettings { name = "WorldLighting" }; AssetDatabase.CreateAsset(ls, lsPath); }
            ls.bakedGI = false;
            ls.realtimeGI = false;
            Lightmapping.lightingSettings = ls;
        }
    }
}
