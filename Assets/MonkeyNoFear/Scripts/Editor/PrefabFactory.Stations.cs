using System.Collections.Generic;
using UnityEditor;
using UnityEngine;
using MonkeyNoFear.Bunker;
using MonkeyNoFear.Core;
using MonkeyNoFear.Interaction;
using MonkeyNoFear.World;

namespace MonkeyNoFear.EditorTools
{
    public static partial class PrefabFactory
    {
        public static void BuildStations()
        {
            MNFPaths.Ensure(StationsDir);
            BuildTerminal();
            BuildSellMachine();
            BuildLocker();
            BuildToolRack();
            BuildDispenser();
            BuildBed();
            BuildGate();
            BuildElevatorParts();
            AssetDatabase.SaveAssets();
        }

        /// <summary>Visual model copy (or fallback box) as a child of a new station root.</summary>
        static GameObject StationRoot(string stationName, string kitObject, Vector3 fallbackSize, string fallbackMat)
        {
            var root = new GameObject(stationName);
            var model = KitLibrary.Copy(kitObject);
            if (model) model.transform.SetParent(root.transform, false);
            else
            {
                Debug.LogWarning($"[MNF] {kitObject} missing from kits — {stationName} uses a placeholder body.");
                Primitive(PrimitiveType.Cube, kitObject, root.transform, Vector3.up * fallbackSize.y * 0.5f, fallbackSize, fallbackMat);
            }
            AddStaticColliders(root);
            Layers.SetLayerRecursive(root, Layers.Environment);
            SurfaceFromMaterials(root);
            return root;
        }

        /// <summary>A physical push button: PokeButton transform with +Y pointing out of its mounting surface.</summary>
        public static PokeButton MakeButton(Transform parent, string name, Vector3 localPos, Vector3 outward, string body, string cap,
            MonoBehaviour receiver, string command, string label, float radius = 0.05f, bool wallMounted = false)
        {
            var b = new GameObject(name);
            b.transform.SetParent(parent, false);
            b.transform.localPosition = localPos;
            // +Y exactly along `outward`; label "up" (local -Z) toward world up, or away from the user on consoles
            var o = outward.normalized;
            var labelUp = Mathf.Abs(Vector3.Dot(o, Vector3.up)) > 0.8f ? Vector3.back : Vector3.up;
            var fwd = -Vector3.ProjectOnPlane(labelUp, o).normalized;
            b.transform.localRotation = Quaternion.LookRotation(fwd, o);
            b.layer = Layers.Interactable;
            // wall-mounted kit buttons face Unity +Z; console buttons face +Y
            var visRot = wallMounted ? Quaternion.Euler(-90f, 0f, 0f) : Quaternion.identity;
            var bodyGo = KitLibrary.Copy(body);
            Vector3 capAt = Vector3.zero;
            if (bodyGo)
            {
                bodyGo.transform.SetParent(b.transform, false);
                bodyGo.transform.localRotation = visRot;
                var sock = KitLibrary.FindDeep(bodyGo.transform, "SOCKET_Cap");
                if (sock) capAt = b.transform.InverseTransformPoint(sock.position);
            }
            var capGo = KitLibrary.Copy(cap);
            if (!capGo)
            {
                capGo = Primitive(PrimitiveType.Cylinder, "Cap", b.transform, Vector3.up * 0.012f, new Vector3(radius * 1.6f, 0.012f, radius * 1.6f), command == "close" || command == "sell" ? "MNF_BulbRed" : "MNF_Plastic_Yellow");
                Object.DestroyImmediate(capGo.GetComponent<Collider>());
            }
            else { capGo.transform.SetParent(b.transform, false); capGo.transform.localRotation = visRot; capGo.transform.localPosition = capAt; }
            var pb = b.AddComponent<PokeButton>();
            pb.receiver = receiver; pb.command = command; pb.cap = capGo.transform; pb.radius = radius; pb.travel = 0.018f;
            pb.capHeight = body == "BigButton_Body" ? 0.048f : body == "TerminalButton_Body" ? 0.022f : 0.012f;
            if (body == "TerminalButton_Body") pb.travel = 0.008f;
            pb.indicator = capGo.GetComponentInChildren<Renderer>();
            if (!string.IsNullOrEmpty(label))
            {
                // label just above the button (local -Z), lying in the button plane, facing out
                var tm = AddText(b.transform, "Label", new Vector3(0f, 0.004f, -radius * 2.1f), Quaternion.Euler(90f, 180f, 0f), 0.016f, TextAnchor.MiddleCenter, new Color(1f, 0.85f, 0.4f), label);
                pb.labelMesh = tm;
                pb.label = label;
            }
            foreach (var t in b.GetComponentsInChildren<Transform>(true)) t.gameObject.layer = Layers.Interactable;
            foreach (var c in b.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
            return pb;
        }

        // ------------------------------------------------------------------ terminal
        static void BuildTerminal()
        {
            var root = StationRoot("Station_Terminal", "Terminal", new Vector3(0.5f, 0.45f, 0.4f), "MNF_MetalPainted_Gray");
            var term = root.AddComponent<BunkerTerminal>();
            var screenQuad = KitLibrary.FindDeep(root.transform, "Screen");
            var screenGo = new GameObject("TerminalScreen");
            if (screenQuad)
            {
                var rot = TextRotationOnQuad(screenQuad, out var n);
                screenGo.transform.SetParent(screenQuad, false);
                screenGo.transform.localRotation = rot;
                screenGo.transform.localPosition = n * 0.003f;
            }
            else
            {
                screenGo.transform.SetParent(root.transform, false);
                screenGo.transform.localPosition = new Vector3(0f, 0.32f, 0.21f);
                screenGo.transform.localRotation = Quaternion.Euler(0f, 180f, 0f);
            }
            var ts = screenGo.AddComponent<TerminalScreen>();
            ts.width = 0.38f; ts.height = 0.29f; ts.rows = 16;
            term.screen = ts;
            // keypad: a flat steel plate on the console front at waist height
            var plate = Primitive(PrimitiveType.Cube, "KeypadPlate", root.transform, new Vector3(0f, 0.94f, 0.36f), new Vector3(0.78f, 0.04f, 0.26f), "MNF_MetalPainted_Gray");
            plate.layer = Layers.Environment;
            string[] cmds = { "prev", "next", "up", "down", "select", "back" };
            string[] labels = { "<PAGE", "PAGE>", "UP", "DOWN", "SELECT", "BACK" };
            for (int i = 0; i < cmds.Length; i++)
            {
                float x = -0.3f + i * 0.12f;
                MakeButton(root.transform, "Key_" + cmds[i], new Vector3(x, 0.96f, 0.34f), Vector3.up, "TerminalButton_Body", "TerminalButton_Cap", term, cmds[i], labels[i], 0.04f, true);
            }
            Save(root, StationsDir, "Station_Terminal");
        }

        // ------------------------------------------------------------------ sell machine
        static void BuildSellMachine()
        {
            var root = StationRoot("Station_SellMachine", "SellMachine", new Vector3(1.0f, 1.4f, 0.8f), "MNF_MetalPainted_Green");
            var st = root.AddComponent<SellStation>();
            var bin = KitLibrary.FindDeep(root.transform, "SOCKET_Bin");
            st.bin.frame = root.transform;
            st.bin.center = bin ? root.transform.InverseTransformPoint(bin.position) + Vector3.down * 0.1f : new Vector3(0f, 0.9f, 0f);
            st.bin.size = new Vector3(0.62f, 0.45f, 0.52f);
            st.tubeOrigin = bin ? bin : root.transform;
            var screenQuad = KitLibrary.FindDeep(root.transform, "Screen");
            Vector3 front = Vector3.forward;
            if (screenQuad)
            {
                var rot = TextRotationOnQuad(screenQuad, out var n);
                st.screen = AddText(screenQuad, "Readout", n * 0.003f, rot, 0.016f, TextAnchor.MiddleCenter, new Color(0.6f, 1f, 0.6f));
                front = root.transform.InverseTransformDirection(screenQuad.TransformDirection(n));
            }
            else st.screen = AddText(root.transform, "Readout", new Vector3(0f, 1.35f, 0.42f), Quaternion.Euler(0, 180, 0), 0.016f, TextAnchor.MiddleCenter, new Color(0.6f, 1f, 0.6f));
            // buttons on the front of the cabinet, below the hopper (cabinet front is at +0.505 m)
            MakeButton(root.transform, "Btn_Sell", new Vector3(-0.3f, 0.62f, 0.51f), Vector3.forward, "BigButton_Body", "BigButton_Cap", st, "sell", "SELL", 0.055f, true);
            MakeButton(root.transform, "Btn_SellPack", new Vector3(0.3f, 0.62f, 0.51f), Vector3.forward, "BigButton_Body", "BigButton_Cap", st, "sellpack", "SELL PACK", 0.055f, true);
            Save(root, StationsDir, "Station_SellMachine");
        }

        // ------------------------------------------------------------------ storage locker
        static void BuildLocker()
        {
            var root = StationRoot("Station_StorageLocker", "StorageLocker", new Vector3(1.2f, 1.6f, 0.6f), "MNF_MetalPainted_Gray");
            var lk = root.AddComponent<StorageLocker>();
            var sock = KitLibrary.FindDeep(root.transform, "SOCKET_Deposit");
            lk.hopper.frame = root.transform;
            lk.hopper.center = sock ? root.transform.InverseTransformPoint(sock.position) : new Vector3(0f, 1.7f, 0f);
            lk.hopper.size = new Vector3(0.9f, 0.45f, 0.5f);
            lk.label = AddText(root.transform, "Label", lk.hopper.center + new Vector3(0f, 0.35f, 0.3f), Quaternion.Euler(0f, 180f, 0f), 0.03f, TextAnchor.MiddleCenter, new Color(1f, 0.85f, 0.4f), "STORAGE");
            Save(root, StationsDir, "Station_StorageLocker");
        }

        // ------------------------------------------------------------------ tool rack
        static void BuildToolRack()
        {
            var root = StationRoot("Station_ToolRack", "ToolRack", new Vector3(2f, 1.2f, 0.15f), "MNF_WoodPlanks");
            var rack = root.AddComponent<ToolRack>();
            for (int i = 0; i < 6; i++)
            {
                var s = KitLibrary.FindDeep(root.transform, "SOCKET_" + i);
                var h = new GameObject("RackSlot_" + i).AddComponent<Holster>();
                h.transform.SetParent(root.transform, false);
                h.transform.localPosition = s ? root.transform.InverseTransformPoint(s.position) : new Vector3(-0.85f + i * 0.34f, 1.1f, 0.12f);
                h.acceptAnyItem = true;
                h.radius = 0.22f;
                h.itemLocalEuler = new Vector3(0f, 90f, 0f); // tools rest horizontally across the forks
                rack.sockets.Add(h);
            }
            Save(root, StationsDir, "Station_ToolRack");
        }

        static void BuildDispenser()
        {
            var root = StationRoot("Station_Dispenser", "Dispenser", new Vector3(0.3f, 0.5f, 0.3f), "MNF_MetalPainted_Yellow");
            var d = root.AddComponent<ItemDispenser>();
            var s = KitLibrary.FindDeep(root.transform, "SOCKET_Out");
            var outlet = new GameObject("Outlet").transform;
            outlet.SetParent(root.transform, false);
            outlet.localPosition = s ? root.transform.InverseTransformPoint(s.position) + Vector3.up * 0.12f : new Vector3(0f, 0.3f, 0.2f);
            d.outlet = outlet;
            AddText(root.transform, "Label", outlet.localPosition + new Vector3(0f, 0.35f, 0.05f), Quaternion.Euler(0f, 180f, 0f), 0.025f, TextAnchor.MiddleCenter, new Color(1f, 0.85f, 0.4f), "DELIVERY");
            Save(root, StationsDir, "Station_Dispenser");
        }

        static void BuildBed()
        {
            var root = StationRoot("Station_Bed", "Bunkbed", new Vector3(1f, 1.8f, 2.1f), "MNF_FabricBlanket");
            var bed = root.AddComponent<BunkBed>();
            var b = KitLibrary.RenderBounds(root);
            MakeButton(root.transform, "Btn_Sleep", new Vector3(b.extents.x + 0.02f, 0.9f, 0f), Vector3.right, "BigButton_Body", "BigButton_Cap", bed, "sleep", "SLEEP", 0.05f, true);
            Save(root, StationsDir, "Station_Bed");
        }

        // ------------------------------------------------------------------ security gate
        static void BuildGate()
        {
            var root = new GameObject("Station_Gate");
            var frame = KitLibrary.Copy("SecurityGate_Frame");
            if (frame) { frame.transform.SetParent(root.transform, false); AddStaticColliders(frame); }
            else
            {
                Primitive(PrimitiveType.Cube, "PostL", root.transform, new Vector3(-1.65f, 1.6f, 0f), new Vector3(0.3f, 3.2f, 0.5f), "MNF_Hazard");
                Primitive(PrimitiveType.Cube, "PostR", root.transform, new Vector3(1.65f, 1.6f, 0f), new Vector3(0.3f, 3.2f, 0.5f), "MNF_Hazard");
                Primitive(PrimitiveType.Cube, "Housing", root.transform, new Vector3(0f, 3.1f, 0f), new Vector3(3.6f, 0.7f, 0.7f), "MNF_MetalPainted_Gray");
            }
            var barsRoot = new GameObject("Bars");
            barsRoot.transform.SetParent(root.transform, false);
            var bars = KitLibrary.Copy("SecurityGate_Bars");
            if (bars) bars.transform.SetParent(barsRoot.transform, false);
            else
                for (int i = 0; i < 11; i++)
                {
                    var bar = Primitive(PrimitiveType.Cylinder, "Bar" + i, barsRoot.transform, new Vector3(-1.4f + i * 0.28f, 1.4f, 0f), new Vector3(0.07f, 1.4f, 0.07f), "MNF_MetalRusted");
                    Object.DestroyImmediate(bar.GetComponent<Collider>());
                }
            ConvertHelperColliders(barsRoot);
            var barCol = barsRoot.GetComponentInChildren<BoxCollider>();
            if (!barCol) { barCol = barsRoot.AddComponent<BoxCollider>(); barCol.center = new Vector3(0f, 1.4f, 0f); barCol.size = new Vector3(3f, 2.8f, 0.2f); }
            var gate = root.AddComponent<SecurityGate>();
            gate.bars = barsRoot.transform;
            gate.barsCollider = barCol;
            gate.openHeight = 2.7f;

            // beacons on the housing corners
            var beacons = new List<Light>(); var rotors = new List<Transform>(); var lamps = new List<Renderer>();
            foreach (float x in new[] { -1.75f, 1.75f })
                foreach (float z in new[] { -0.35f, 0.35f })
                {
                    var bgo = KitLibrary.Copy("WarningBeacon") ?? Primitive(PrimitiveType.Sphere, "Beacon", null, Vector3.zero, Vector3.one * 0.15f, "MNF_BulbRed");
                    bgo.transform.SetParent(root.transform, false);
                    bgo.transform.localPosition = new Vector3(x, 3.0f, z);
                    bgo.transform.localRotation = Quaternion.LookRotation(z > 0 ? Vector3.forward : Vector3.back);
                    var rotor = new GameObject("Rotor").transform;
                    rotor.SetParent(bgo.transform, false);
                    rotor.localPosition = Vector3.forward * 0.12f;
                    var l = AddLight(rotor, "Sweep", LightType.Spot, new Color(1f, 0.55f, 0.1f), 9f, 2.2f, Vector3.zero);
                    l.spotAngle = 50f; l.transform.localRotation = Quaternion.Euler(0f, 90f, 0f); l.enabled = false;
                    beacons.Add(l); rotors.Add(rotor);
                    var lampT = KitLibrary.FindDeep(bgo.transform, "Lamp");
                    var lr = lampT ? lampT.GetComponent<Renderer>() : bgo.GetComponentInChildren<Renderer>();
                    if (lr) lamps.Add(lr);
                }
            gate.beacons = beacons.ToArray();
            gate.beaconRotors = rotors.ToArray();
            gate.statusLamps = lamps.ToArray();

            // button panels: inside on the bunker wall east of the gate (facing -Z, into the hall), outside on
            // the corridor's west wall just past the gate (facing +X, into the corridor)
            var openB = new List<PokeButton>(); var closeB = new List<PokeButton>();
            var panels = new[] { (pos: new Vector3(2.35f, 1.25f, -0.18f), dir: Vector3.back, size: new Vector3(0.45f, 0.6f, 0.05f), name: "PanelInside"),
                                 (pos: new Vector3(-1.98f, 1.25f, 1.4f), dir: Vector3.right, size: new Vector3(0.05f, 0.6f, 0.45f), name: "PanelOutside") };
            foreach (var pn in panels)
            {
                var panel = Primitive(PrimitiveType.Cube, pn.name, root.transform, pn.pos, pn.size, "MNF_MetalPainted_Yellow");
                panel.layer = Layers.Environment;
                var basePos = pn.pos + pn.dir * 0.03f;
                openB.Add(MakeButton(root.transform, "Open_" + pn.name, basePos + Vector3.up * 0.13f, pn.dir, "BigButton_Body", "BigButton_Cap", gate, "open", "OPEN", 0.06f, true));
                closeB.Add(MakeButton(root.transform, "Close_" + pn.name, basePos - Vector3.up * 0.15f, pn.dir, "BigButton_Body", "BigButton_Cap", gate, "close", "CLOSE", 0.06f, true));
            }
            gate.openButtons = openB.ToArray();
            gate.closeButtons = closeB.ToArray();

            // manual override lever on the inside wall
            MakeLever(root.transform, new Vector3(-2.35f, 1.3f, -0.15f), Vector3.back, gate, "override", "override", "MANUAL\nOVERRIDE");
            Layers.SetLayerRecursive(barsRoot, Layers.Environment);
            if (frame) Layers.SetLayerRecursive(frame, Layers.Environment);
            Save(root, StationsDir, "Station_Gate");
        }

        public static PhysicalLever MakeLever(Transform parent, Vector3 localPos, Vector3 outward, MonoBehaviour receiver, string cmdDown, string cmdUp, string label)
        {
            var root = new GameObject("Lever");
            root.transform.SetParent(parent, false);
            root.transform.localPosition = localPos;
            root.transform.localRotation = Quaternion.LookRotation(outward.normalized, Vector3.up);
            var baseGo = KitLibrary.Copy("Lever_Base");
            if (baseGo) baseGo.transform.SetParent(root.transform, false);
            else Primitive(PrimitiveType.Cube, "Base", root.transform, Vector3.zero, new Vector3(0.18f, 0.3f, 0.06f), "MNF_MetalPainted_Red");
            var hinge = new GameObject("Hinge").transform;
            hinge.SetParent(root.transform, false);
            var sock = baseGo ? KitLibrary.FindDeep(baseGo.transform, "SOCKET_Handle") : null;
            hinge.localPosition = sock ? root.transform.InverseTransformPoint(sock.position) : new Vector3(0f, 0f, 0.07f);
            // the handle is authored pointing straight out of the wall (+Z); it pivots about X
            var handle = KitLibrary.Copy("Lever_Handle");
            if (handle) handle.transform.SetParent(hinge, false);
            else { var h = Primitive(PrimitiveType.Cylinder, "Handle", hinge, new Vector3(0f, 0f, 0.17f), new Vector3(0.04f, 0.17f, 0.04f), "MNF_Rubber"); h.transform.localRotation = Quaternion.Euler(90f, 0f, 0f); }
            foreach (var c in root.GetComponentsInChildren<Collider>(true)) Object.DestroyImmediate(c);
            // grab volume follows the handle (child of the hinge), covering the T-grip end
            var grip = new GameObject("GripVolume");
            grip.transform.SetParent(hinge, false);
            var grabCol = grip.AddComponent<BoxCollider>();
            grabCol.center = new Vector3(0f, 0f, 0.26f); grabCol.size = new Vector3(0.16f, 0.12f, 0.24f); grabCol.isTrigger = true;
            var lever = hinge.gameObject.AddComponent<PhysicalLever>();
            lever.receiver = receiver; lever.commandDown = cmdDown; lever.commandUp = cmdUp; lever.hinge = hinge;
            // hand angle from straight up (0) toward the front (+90): handle starts raised, pull it down
            lever.minAngle = 40f; lever.maxAngle = 140f; lever.restAngle = 40f; lever.visualAngleOffset = -90f; lever.springReturn = true;
            if (!string.IsNullOrEmpty(label))
                AddText(root.transform, "Label", new Vector3(0f, 0.32f, 0.04f), Quaternion.Euler(0f, 180f, 0f), 0.022f, TextAnchor.LowerCenter, new Color(1f, 0.85f, 0.4f), label);
            Layers.SetLayerRecursive(root, Layers.Interactable);
            return lever;
        }

        // ------------------------------------------------------------------ elevator
        static void BuildElevatorParts()
        {
            var root = new GameObject("Station_ElevatorPlatform");
            var plat = KitLibrary.Copy("Elevator_Platform");
            if (plat) plat.transform.SetParent(root.transform, false);
            else Primitive(PrimitiveType.Cube, "Floor", root.transform, Vector3.up * -0.05f, new Vector3(3f, 0.1f, 3f), "MNF_MetalGrate");
            AddStaticColliders(root);
            Layers.SetLayerRecursive(root, Layers.Environment);
            root.AddComponent<Player.MovingPlatform>();
            SurfaceFromMaterials(root);
            Save(root, StationsDir, "Station_ElevatorPlatform");
        }
    }
}
