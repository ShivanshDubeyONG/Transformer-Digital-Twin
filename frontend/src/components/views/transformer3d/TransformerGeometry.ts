import * as THREE from 'three';

export type ComponentId = 'tank' | 'l1' | 'l2' | 'l3' | 'neutral' | 'cooling' | 'oil' | 'core';

export type VisualMode = 'realistic' | 'thermal' | 'xray' | 'electrical';

export interface ComponentMeshRef {
  id: ComponentId;
  group: THREE.Group | THREE.Mesh;
  anchorPoint: THREE.Vector3;
}

export interface ModelTelemetry {
  topOilTemp?: number | null;
  ambientTemp?: number | null;
  currentL1?: number | null;
  currentL2?: number | null;
  currentL3?: number | null;
  neutralCurrent?: number | null;
  oilLevelPct?: number | null;
  relativeLoad?: number | null;
  thermalStatus?: string;
  phaseStatus?: string;
  oilStatus?: string;
}

export interface ExplodablePart {
  object: THREE.Object3D;
  basePosition: THREE.Vector3;
  baseRotation: THREE.Euler;
  explodeOffset: THREE.Vector3;
  explodeRotation?: THREE.Euler;
}

export interface ComponentAnchorTrack {
  id: ComponentId;
  baseAnchor: THREE.Vector3;
  explodeOffset: THREE.Vector3;
}

export class TransformerSceneBuilder {
  public rootGroup: THREE.Group;
  public componentRefs: Map<ComponentId, ComponentMeshRef>;
  public interactiveMeshes: THREE.Mesh[];

  // Dynamic references
  private tankMesh: THREE.Mesh | null = null;
  private tankFlange: THREE.Mesh | null = null;
  private coreGroup: THREE.Group | null = null;
  private radiatorGroup: THREE.Group | null = null;
  private conservatorGroup: THREE.Group | null = null;
  private needleMesh: THREE.Mesh | null = null;
  private particleGroup: THREE.Group | null = null;
  private currentSparks: THREE.Points[] = [];

  // Exploded / Disassembly animation state
  private explodableParts: ExplodablePart[] = [];
  private anchorTracks: ComponentAnchorTrack[] = [];
  private topYoke: THREE.Mesh | null = null;
  private bottomYoke: THREE.Mesh | null = null;
  private coreLimbs: {
    limb: THREE.Mesh;
    winding: THREE.Mesh;
    baseLimbPos: THREE.Vector3;
    baseWindingPos: THREE.Vector3;
    offset: THREE.Vector3;
  }[] = [];
  private currentExplodeFactor: number = 0;
  private currentVisualMode: VisualMode = 'realistic';

  // Material storage for mode switching
  private standardMaterials: Map<THREE.Mesh, THREE.Material | THREE.Material[]> = new Map();

  // Highlight state
  private selectedComponentId: ComponentId | null = null;
  private hoveredComponentId: ComponentId | null = null;

  constructor() {
    this.rootGroup = new THREE.Group();
    this.componentRefs = new Map();
    this.interactiveMeshes = [];
    this.buildScene();
  }

  private registerInteractive(mesh: THREE.Mesh, id: ComponentId, anchor?: THREE.Vector3) {
    mesh.userData = { componentId: id };
    this.interactiveMeshes.push(mesh);
    this.standardMaterials.set(mesh, mesh.material);

    if (!this.componentRefs.has(id)) {
      this.componentRefs.set(id, {
        id,
        group: mesh,
        anchorPoint: anchor ? anchor.clone() : mesh.position.clone(),
      });
    }
  }

  private registerExplodable(
    object: THREE.Object3D,
    explodeOffset: THREE.Vector3,
    explodeRotation?: THREE.Euler
  ) {
    this.explodableParts.push({
      object,
      basePosition: object.position.clone(),
      baseRotation: object.rotation.clone(),
      explodeOffset: explodeOffset.clone(),
      explodeRotation: explodeRotation ? explodeRotation.clone() : undefined,
    });
  }

  private registerAnchorTrack(
    id: ComponentId,
    baseAnchor: THREE.Vector3,
    explodeOffset: THREE.Vector3
  ) {
    this.anchorTracks.push({
      id,
      baseAnchor: baseAnchor.clone(),
      explodeOffset: explodeOffset.clone(),
    });
  }

  private buildScene() {
    // -------------------------------------------------------------------------
    // Authentic Substation Utility Material Palette (ANSI 70 / ANSI 61 Utility Steel)
    // Clean, crisp industrial finish with subtle matte-satin specular response (not dull, not shiny)
    // -------------------------------------------------------------------------
    const paintedSteelMat = new THREE.MeshStandardMaterial({
      color: 0x64707d, // Authentic utility transformer light gray (ANSI 70 / ANSI 61)
      roughness: 0.44, // Clean matte-satin technical finish, zero plastic gloss
      metalness: 0.16, // Painted heavy sheet steel
    });

    const structuralSteelMat = new THREE.MeshStandardMaterial({
      color: 0x3d4550, // Contrasting deep structural slate-steel for base skids and cover flange
      roughness: 0.50,
      metalness: 0.32,
    });

    const radiatorFinMat = new THREE.MeshStandardMaterial({
      color: 0x54606e, // Distinct technical cooling fin plates (subtle contrast against tank)
      roughness: 0.46,
      metalness: 0.22,
    });

    const pipeMat = new THREE.MeshStandardMaterial({
      color: 0x424a54, // Industrial dark steel seamless pipe
      roughness: 0.42,
      metalness: 0.35,
    });

    const porcelainGlazeMat = new THREE.MeshStandardMaterial({
      color: 0x733822, // Rich technical electrical glazed porcelain (warm technical terracotta/umber glaze)
      roughness: 0.20, // Ceramic glaze sheen without excessive reflection
      metalness: 0.08,
    });

    const copperMat = new THREE.MeshStandardMaterial({
      color: 0xc86a3b, // Natural electrical copper
      roughness: 0.28,
      metalness: 0.82,
    });

    const brassMat = new THREE.MeshStandardMaterial({
      color: 0xcfa036, // Machined brass fittings and valves
      roughness: 0.30,
      metalness: 0.78,
    });

    // -------------------------------------------------------------------------
    // 1. Digital Twin Studio Foundation Pad & Ground Grid
    // -------------------------------------------------------------------------
    // Clean neutral studio ground grid
    const gridHelper = new THREE.GridHelper(9.6, 24, 0x4a4d56, 0x1d1f24);
    gridHelper.position.set(0, -1.58, 0);
    const gridMat = gridHelper.material as THREE.LineBasicMaterial;
    gridMat.transparent = true;
    gridMat.opacity = 0.25;
    this.rootGroup.add(gridHelper);

    // Subtle concentric accent ring
    const ringGeo = new THREE.RingGeometry(3.6, 3.68, 64);
    const ringMat = new THREE.MeshBasicMaterial({
      color: 0x4a4d56,
      transparent: true,
      opacity: 0.22,
      side: THREE.DoubleSide,
    });
    const ring = new THREE.Mesh(ringGeo, ringMat);
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(0, -1.575, 0);
    this.rootGroup.add(ring);

    // Soft radial contact shadow directly underneath the assembly
    const shadowCanvas = document.createElement('canvas');
    shadowCanvas.width = 128;
    shadowCanvas.height = 128;
    const ctx = shadowCanvas.getContext('2d');
    if (ctx) {
      const grad = ctx.createRadialGradient(64, 64, 12, 64, 64, 60);
      grad.addColorStop(0, 'rgba(0, 0, 0, 0.7)');
      grad.addColorStop(0.5, 'rgba(0, 0, 0, 0.3)');
      grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, 128, 128);
    }
    const shadowTex = new THREE.CanvasTexture(shadowCanvas);
    const shadowGeo = new THREE.PlaneGeometry(7.6, 5.6);
    const shadowMat = new THREE.MeshBasicMaterial({
      map: shadowTex,
      transparent: true,
      depthWrite: false,
    });
    const contactShadow = new THREE.Mesh(shadowGeo, shadowMat);
    contactShadow.rotation.x = -Math.PI / 2;
    contactShadow.position.set(0, -1.57, 0);
    this.rootGroup.add(contactShadow);

    // Concrete Plinth Pad (Crisp substation foundation)
    const padGeo = new THREE.BoxGeometry(5.8, 0.22, 4.2);
    const padMat = new THREE.MeshStandardMaterial({
      color: 0x3b424d, // Clean architectural substation concrete pad
      roughness: 0.85,
      metalness: 0.08,
    });
    const concretePad = new THREE.Mesh(padGeo, padMat);
    concretePad.position.set(0, -1.48, 0);
    concretePad.receiveShadow = true;
    this.rootGroup.add(concretePad);

    // Structural Steel Skid Runners (Dual I-beams)
    const beamGeo = new THREE.BoxGeometry(5.2, 0.16, 0.2);
    const skid1 = new THREE.Mesh(beamGeo, structuralSteelMat);
    skid1.position.set(0, -1.28, 1.15);
    const skid2 = new THREE.Mesh(beamGeo, structuralSteelMat);
    skid2.position.set(0, -1.28, -1.15);
    this.rootGroup.add(skid1, skid2);

    // -------------------------------------------------------------------------
    // 2. Main Tank Body & Lid (Separated for Disassembly Animation)
    // -------------------------------------------------------------------------
    const tankWidth = 3.6;
    const tankHeight = 2.1;
    const tankDepth = 2.0;

    // Tank Body Group (slides downwards in exploded view)
    const tankBodyGroup = new THREE.Group();

    // Tank Core Box
    const tankGeo = new THREE.BoxGeometry(tankWidth, tankHeight, tankDepth);
    this.tankMesh = new THREE.Mesh(tankGeo, paintedSteelMat);
    this.tankMesh.position.set(0, 0, 0);
    this.tankMesh.castShadow = true;
    this.tankMesh.receiveShadow = true;
    this.registerInteractive(this.tankMesh, 'tank', new THREE.Vector3(0, 0.5, 1.15));
    tankBodyGroup.add(this.tankMesh);

    // Front Metal Rating Plate
    const plaqueGeo = new THREE.BoxGeometry(0.65, 0.32, 0.02);
    const plaqueMat = new THREE.MeshStandardMaterial({
      color: 0x22262d,
      roughness: 0.32,
      metalness: 0.85,
    });
    const plaque = new THREE.Mesh(plaqueGeo, plaqueMat);
    plaque.position.set(0, -0.5, tankDepth / 2 + 0.015);
    tankBodyGroup.add(plaque);

    // Oil Sampling / Drain Valve
    const valveGeo = new THREE.CylinderGeometry(0.06, 0.06, 0.22, 16);
    const valve = new THREE.Mesh(valveGeo, brassMat);
    valve.rotation.z = Math.PI / 2;
    valve.position.set(tankWidth / 2 + 0.12, -0.75, 0.5);
    const valveHandle = new THREE.Mesh(new THREE.TorusGeometry(0.065, 0.016, 8, 16), brassMat);
    valveHandle.position.set(tankWidth / 2 + 0.24, -0.75, 0.5);
    valveHandle.rotation.y = Math.PI / 2;
    tankBodyGroup.add(valve, valveHandle);

    this.rootGroup.add(tankBodyGroup);
    this.registerExplodable(tankBodyGroup, new THREE.Vector3(0, -0.35, 0));
    this.registerAnchorTrack('tank', new THREE.Vector3(0, 0.5, 1.15), new THREE.Vector3(0, -0.35, 0));

    // Tank Lid Group (lifts upwards in exploded view)
    const tankLidGroup = new THREE.Group();

    // Tank Top Cover Flange
    const flangeGeo = new THREE.BoxGeometry(tankWidth + 0.22, 0.12, tankDepth + 0.22);
    this.tankFlange = new THREE.Mesh(flangeGeo, structuralSteelMat);
    this.tankFlange.position.set(0, tankHeight / 2 + 0.06, 0);
    this.tankFlange.castShadow = true;
    this.registerInteractive(this.tankFlange, 'tank');
    tankLidGroup.add(this.tankFlange);

    // Top-Oil Temperature Well Pocket (Brass housing on tank top cover)
    const probeWellGeo = new THREE.CylinderGeometry(0.065, 0.065, 0.24, 16);
    const probeWell = new THREE.Mesh(probeWellGeo, brassMat);
    probeWell.position.set(0.5, tankHeight / 2 + 0.18, 0.35);
    this.registerInteractive(probeWell, 'tank', new THREE.Vector3(0.5, tankHeight / 2 + 0.35, 0.35));
    tankLidGroup.add(probeWell);

    this.rootGroup.add(tankLidGroup);
    this.registerExplodable(tankLidGroup, new THREE.Vector3(0, 0.95, 0));

    // -------------------------------------------------------------------------
    // 3. Cooling Radiators (Evenly Spaced, Aligned & Physically Coherent)
    // -------------------------------------------------------------------------
    this.radiatorGroup = new THREE.Group();

    const createRadiatorBank = (isLeft: boolean) => {
      const bankGroup = new THREE.Group();
      const xSign = isLeft ? -1 : 1;
      const bankX = xSign * (tankWidth / 2 + 0.52);

      // Upper & Lower Header Feeder Pipes connecting cleanly to tank
      const topPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.5, 16), pipeMat);
      topPipe.rotation.z = Math.PI / 2;
      topPipe.position.set(xSign * (tankWidth / 2 + 0.25), 0.75, 0);

      const botPipe = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.09, 0.5, 16), pipeMat);
      botPipe.rotation.z = Math.PI / 2;
      botPipe.position.set(xSign * (tankWidth / 2 + 0.25), -0.75, 0);

      // Longitudinal Manifold Header Tubes
      const manifoldGeo = new THREE.CylinderGeometry(0.09, 0.09, 1.6, 16);
      const topManifold = new THREE.Mesh(manifoldGeo, pipeMat);
      topManifold.rotation.x = Math.PI / 2;
      topManifold.position.set(bankX, 0.75, 0);

      const botManifold = new THREE.Mesh(manifoldGeo, pipeMat);
      botManifold.rotation.x = Math.PI / 2;
      botManifold.position.set(bankX, -0.75, 0);

      bankGroup.add(topPipe, botPipe, topManifold, botManifold);

      // Evenly spaced cooling fins (7 plates per bank)
      const finCount = 7;
      const finSpacing = 0.22;
      for (let i = 0; i < finCount; i++) {
        const z = -0.66 + i * finSpacing;
        const finGeo = new THREE.BoxGeometry(0.58, 1.45, 0.035);
        const fin = new THREE.Mesh(finGeo, radiatorFinMat);
        fin.position.set(bankX, 0, z);
        fin.castShadow = true;
        this.registerInteractive(fin, 'cooling', new THREE.Vector3(bankX, 0.1, 0));
        bankGroup.add(fin);
      }

      return bankGroup;
    };

    const leftBank = createRadiatorBank(true);
    const rightBank = createRadiatorBank(false);
    this.radiatorGroup.add(leftBank, rightBank);
    this.rootGroup.add(this.radiatorGroup);

    this.registerExplodable(leftBank, new THREE.Vector3(-1.20, 0, 0));
    this.registerExplodable(rightBank, new THREE.Vector3(1.20, 0, 0));
    this.registerAnchorTrack(
      'cooling',
      new THREE.Vector3(-(tankWidth / 2 + 0.52), 0.1, 0),
      new THREE.Vector3(-1.20, 0, 0)
    );

    // -------------------------------------------------------------------------
    // 4. Conservator Tank, Buchholz Relay & Silica Breather
    // -------------------------------------------------------------------------
    this.conservatorGroup = new THREE.Group();

    // Conservator Drum Body
    const drumGeo = new THREE.CylinderGeometry(0.44, 0.44, 2.3, 32);
    const drum = new THREE.Mesh(drumGeo, paintedSteelMat);
    drum.rotation.z = Math.PI / 2;
    drum.position.set(0.2, 2.05, -0.75);
    drum.castShadow = true;
    this.registerInteractive(drum, 'oil', new THREE.Vector3(0.2, 2.2, -0.75));
    this.conservatorGroup.add(drum);

    // Domed Endcaps
    const capGeo = new THREE.SphereGeometry(0.44, 20, 14, 0, Math.PI * 2, 0, Math.PI / 2);
    const leftCap = new THREE.Mesh(capGeo, paintedSteelMat);
    leftCap.rotation.z = -Math.PI / 2;
    leftCap.position.set(-0.95, 2.05, -0.75);
    const rightCap = new THREE.Mesh(capGeo, paintedSteelMat);
    rightCap.rotation.z = Math.PI / 2;
    rightCap.position.set(1.35, 2.05, -0.75);
    this.conservatorGroup.add(leftCap, rightCap);

    // Support Struts to Tank Top Cover
    const legGeo = new THREE.BoxGeometry(0.08, 0.9, 0.08);
    const leg1 = new THREE.Mesh(legGeo, pipeMat);
    leg1.position.set(-0.55, 1.55, -0.75);
    const leg2 = new THREE.Mesh(legGeo, pipeMat);
    leg2.position.set(0.95, 1.55, -0.75);
    this.conservatorGroup.add(leg1, leg2);

    // Buchholz Pipe (Connecting Tank to Conservator with In-Line Relay)
    const buchholzCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0.2, tankHeight / 2 + 0.06, -0.25),
      new THREE.Vector3(0.2, 1.6, -0.45),
      new THREE.Vector3(0.2, 1.85, -0.65),
      new THREE.Vector3(0.2, 2.05, -0.75),
    ]);
    const buchholzPipe = new THREE.Mesh(
      new THREE.TubeGeometry(buchholzCurve, 20, 0.06, 16, false),
      pipeMat
    );
    const buchholzBoxGeo = new THREE.BoxGeometry(0.22, 0.24, 0.22);
    const buchholzBox = new THREE.Mesh(buchholzBoxGeo, brassMat);
    buchholzBox.position.set(0.2, 1.6, -0.45);
    this.registerInteractive(buchholzBox, 'oil', new THREE.Vector3(0.2, 1.7, -0.45));
    this.conservatorGroup.add(buchholzPipe, buchholzBox);

    // Magnetic Oil Gauge (MOG) Face & Needle
    const mogDialGeo = new THREE.CylinderGeometry(0.18, 0.18, 0.04, 24);
    const dialFaceMat = new THREE.MeshStandardMaterial({
      color: 0xe5e7eb,
      roughness: 0.2,
      metalness: 0.1,
    });
    const mogDial = new THREE.Mesh(mogDialGeo, dialFaceMat);
    mogDial.rotation.x = Math.PI / 2;
    mogDial.position.set(1.38, 2.05, -0.75);

    const needleGeo = new THREE.BoxGeometry(0.015, 0.12, 0.015);
    const needleMat = new THREE.MeshStandardMaterial({
      color: 0x22262d,
      roughness: 0.25,
      metalness: 0.8,
    });
    this.needleMesh = new THREE.Mesh(needleGeo, needleMat);
    this.needleMesh.position.set(1.41, 2.05, -0.75);
    this.conservatorGroup.add(mogDial, this.needleMesh);

    // Dehydrating Silica Gel Breather
    const breatherPipeGeo = new THREE.CylinderGeometry(0.03, 0.03, 0.7, 12);
    const breatherPipe = new THREE.Mesh(breatherPipeGeo, pipeMat);
    breatherPipe.position.set(1.32, 1.5, -0.45);

    const silicaCanisterGeo = new THREE.CylinderGeometry(0.09, 0.09, 0.3, 16);
    const silicaMat = new THREE.MeshStandardMaterial({
      color: 0x365a8c, // Muted technical desiccant blue
      roughness: 0.25,
      metalness: 0.1,
      transparent: true,
      opacity: 0.8,
    });
    const silicaCanister = new THREE.Mesh(silicaCanisterGeo, silicaMat);
    silicaCanister.position.set(1.32, 1.05, -0.45);
    this.conservatorGroup.add(breatherPipe, silicaCanister);

    this.rootGroup.add(this.conservatorGroup);
    this.registerExplodable(
      this.conservatorGroup,
      new THREE.Vector3(0, 0.90, -0.85),
      new THREE.Euler(-0.06, 0, 0)
    );
    this.registerAnchorTrack(
      'oil',
      new THREE.Vector3(0.2, 2.2, -0.75),
      new THREE.Vector3(0, 0.90, -0.85)
    );

    // -------------------------------------------------------------------------
    // 5. HV Condenser Bushings (Phase L1, L2, L3)
    // -------------------------------------------------------------------------
    const createHVBushing = (
      id: ComponentId,
      x: number,
      z: number,
      phaseColor: number
    ) => {
      const bushingGroup = new THREE.Group();

      // Rounded Turret Base
      const turretGeo = new THREE.CylinderGeometry(0.18, 0.22, 0.18, 20);
      const turret = new THREE.Mesh(turretGeo, structuralSteelMat);
      turret.position.set(0, 0.09, 0);
      bushingGroup.add(turret);

      // Glazed Porcelain Sheds (5 conical sheds)
      const shedCount = 5;
      for (let s = 0; s < shedCount; s++) {
        const shedY = 0.26 + s * 0.19;
        const shedGeo = new THREE.CylinderGeometry(0.08, 0.2, 0.13, 20);
        const shed = new THREE.Mesh(shedGeo, porcelainGlazeMat);
        shed.position.set(0, shedY, 0);
        shed.castShadow = true;
        this.registerInteractive(shed, id, new THREE.Vector3(x, tankHeight / 2 + 1.2, z));
        bushingGroup.add(shed);
      }

      // Restrained Phase Color Collar
      const collarGeo = new THREE.CylinderGeometry(0.11, 0.11, 0.06, 16);
      const collarMat = new THREE.MeshStandardMaterial({
        color: phaseColor,
        roughness: 0.35,
        metalness: 0.5,
      });
      const collar = new THREE.Mesh(collarGeo, collarMat);
      collar.position.set(0, 0.21, 0);
      bushingGroup.add(collar);

      // Terminal Stud & Lug
      const stemGeo = new THREE.CylinderGeometry(0.03, 0.03, 0.26, 16);
      const stem = new THREE.Mesh(stemGeo, copperMat);
      stem.position.set(0, 1.35, 0);

      const terminalLug = new THREE.Mesh(new THREE.SphereGeometry(0.06, 16, 16), brassMat);
      terminalLug.position.set(0, 1.48, 0);
      this.registerInteractive(terminalLug, id);

      bushingGroup.add(stem, terminalLug);
      bushingGroup.position.set(x, tankHeight / 2 + 0.12, z);
      return bushingGroup;
    };

    // Phase collars: standard industrial IEC phase identification
    const bushingL1 = createHVBushing('l1', -0.9, 0.25, 0xef4444); // Phase L1 (Red)
    const bushingL2 = createHVBushing('l2', 0.0, 0.25, 0xf59e0b);  // Phase L2 (Amber/Yellow)
    const bushingL3 = createHVBushing('l3', 0.9, 0.25, 0x3b82f6);  // Phase L3 (Blue)
    this.rootGroup.add(bushingL1, bushingL2, bushingL3);

    this.registerExplodable(bushingL1, new THREE.Vector3(-0.35, 1.45, 0.35));
    this.registerExplodable(bushingL2, new THREE.Vector3(0.0, 1.65, 0.40));
    this.registerExplodable(bushingL3, new THREE.Vector3(0.35, 1.45, 0.35));

    this.registerAnchorTrack(
      'l1',
      new THREE.Vector3(-0.9, tankHeight / 2 + 1.2, 0.25),
      new THREE.Vector3(-0.35, 1.45, 0.35)
    );
    this.registerAnchorTrack(
      'l2',
      new THREE.Vector3(0.0, tankHeight / 2 + 1.2, 0.25),
      new THREE.Vector3(0.0, 1.65, 0.40)
    );
    this.registerAnchorTrack(
      'l3',
      new THREE.Vector3(0.9, tankHeight / 2 + 1.2, 0.25),
      new THREE.Vector3(0.35, 1.45, 0.35)
    );

    // -------------------------------------------------------------------------
    // 6. Neutral Bushing (Phase N) & Ground Earthing Lead
    // -------------------------------------------------------------------------
    const neutralGroup = new THREE.Group();
    const neutralTurretGeo = new THREE.CylinderGeometry(0.12, 0.15, 0.14, 16);
    const neutralTurret = new THREE.Mesh(neutralTurretGeo, structuralSteelMat);
    neutralTurret.position.set(0, 0.07, 0);

    const neutralPorcelainMat = new THREE.MeshStandardMaterial({
      color: 0xa0aec0, // Light neutral porcelain
      roughness: 0.18,
      metalness: 0.12,
    });

    for (let s = 0; s < 3; s++) {
      const shedGeo = new THREE.CylinderGeometry(0.06, 0.14, 0.1, 16);
      const shed = new THREE.Mesh(shedGeo, neutralPorcelainMat);
      shed.position.set(0, 0.19 + s * 0.14, 0);
      this.registerInteractive(shed, 'neutral', new THREE.Vector3(-1.45, tankHeight / 2 + 0.55, 0.25));
      neutralGroup.add(shed);
    }

    const neutralLug = new THREE.Mesh(new THREE.SphereGeometry(0.045, 12, 12), brassMat);
    neutralLug.position.set(0, 0.65, 0);
    neutralGroup.add(neutralTurret, neutralLug);

    // Grounding copper strap running cleanly down the tank wall
    const groundCurve = new THREE.CatmullRomCurve3([
      new THREE.Vector3(0, 0.65, 0),
      new THREE.Vector3(-0.2, 0.15, 0.08),
      new THREE.Vector3(-0.28, -0.8, 0.12),
      new THREE.Vector3(-0.3, -tankHeight - 0.1, 0.15),
    ]);
    const groundStrap = new THREE.Mesh(
      new THREE.TubeGeometry(groundCurve, 16, 0.018, 8, false),
      copperMat
    );
    neutralGroup.add(groundStrap);

    neutralGroup.position.set(-1.45, tankHeight / 2 + 0.12, 0.25);
    this.rootGroup.add(neutralGroup);
    this.registerExplodable(neutralGroup, new THREE.Vector3(-0.60, 1.35, 0.25));
    this.registerAnchorTrack(
      'neutral',
      new THREE.Vector3(-1.45, tankHeight / 2 + 0.55, 0.25),
      new THREE.Vector3(-0.60, 1.35, 0.25)
    );

    // -------------------------------------------------------------------------
    // 7. Internal Magnetic Core & Windings (Visible in X-Ray / Thermal Heatmap / Disassembly)
    // -------------------------------------------------------------------------
    this.coreGroup = new THREE.Group();
    const coreMat = new THREE.MeshStandardMaterial({
      color: 0x474a52,
      roughness: 0.5,
      metalness: 0.7,
    });

    const yokeGeo = new THREE.BoxGeometry(2.6, 0.28, 0.45);
    this.bottomYoke = new THREE.Mesh(yokeGeo, coreMat);
    this.bottomYoke.position.set(0, -0.7, 0);
    this.topYoke = new THREE.Mesh(yokeGeo, coreMat);
    this.topYoke.position.set(0, 0.7, 0);
    this.coreGroup.add(this.bottomYoke, this.topYoke);

    const limbGeo = new THREE.BoxGeometry(0.4, 1.15, 0.4);
    const limbConfigs = [
      { x: -0.8, offset: new THREE.Vector3(-0.25, 0, -0.22) },
      { x: 0.0, offset: new THREE.Vector3(0.0, 0, 0.22) },
      { x: 0.8, offset: new THREE.Vector3(0.25, 0, -0.22) },
    ];

    limbConfigs.forEach(({ x, offset }) => {
      const limb = new THREE.Mesh(limbGeo, coreMat);
      limb.position.set(x, 0, 0);
      this.coreGroup!.add(limb);

      const windingGeo = new THREE.CylinderGeometry(0.38, 0.38, 1.05, 24);
      const winding = new THREE.Mesh(windingGeo, copperMat);
      winding.position.set(x, 0, 0);
      this.registerInteractive(winding, 'core', new THREE.Vector3(x, 0.15, 0));
      this.coreGroup!.add(winding);

      this.coreLimbs.push({
        limb,
        winding,
        baseLimbPos: limb.position.clone(),
        baseWindingPos: winding.position.clone(),
        offset,
      });
    });

    this.coreGroup.visible = false;
    this.rootGroup.add(this.coreGroup);
    this.registerAnchorTrack(
      'core',
      new THREE.Vector3(0, 0.15, 0),
      new THREE.Vector3(0, 0.20, 0.15)
    );

    // -------------------------------------------------------------------------
    // 8. Electrical Flow Particles (Restrained Particle Line)
    // -------------------------------------------------------------------------
    this.particleGroup = new THREE.Group();
    const sparkPositions = [
      new THREE.Vector3(-0.9, tankHeight / 2 + 1.6, 0.25),
      new THREE.Vector3(0.0, tankHeight / 2 + 1.6, 0.25),
      new THREE.Vector3(0.9, tankHeight / 2 + 1.6, 0.25),
      new THREE.Vector3(-1.45, tankHeight / 2 + 0.8, 0.25),
    ];

    sparkPositions.forEach((pos, idx) => {
      const pCount = 12;
      const pGeo = new THREE.BufferGeometry();
      const pPos = new Float32Array(pCount * 3);
      for (let i = 0; i < pCount; i++) {
        pPos[i * 3] = (Math.random() - 0.5) * 0.08;
        pPos[i * 3 + 1] = Math.random() * 0.25;
        pPos[i * 3 + 2] = (Math.random() - 0.5) * 0.08;
      }
      pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
      const pMat = new THREE.PointsMaterial({
        color: idx === 3 ? 0x42c7d5 : 0xe0a040,
        size: 0.035,
        transparent: true,
        opacity: 0.75,
      });
      const pSys = new THREE.Points(pGeo, pMat);
      pSys.position.copy(pos);
      this.currentSparks.push(pSys);
      this.particleGroup!.add(pSys);
    });

    this.particleGroup.visible = false;
    this.rootGroup.add(this.particleGroup);
  }

  // ---------------------------------------------------------------------------
  // Telemetry & State Binding
  // ---------------------------------------------------------------------------
  public updateTelemetry(telemetry: ModelTelemetry) {
    if (this.needleMesh) {
      const oilLevel = telemetry.oilLevelPct ?? 50;
      const angle = -Math.PI * 0.6 + (oilLevel / 100) * (Math.PI * 1.2);
      this.needleMesh.rotation.x = angle;
    }

    if (this.particleGroup && this.particleGroup.visible) {
      this.currentSparks.forEach((pts) => {
        const pos = pts.geometry.attributes.position as THREE.BufferAttribute;
        for (let i = 0; i < pos.count; i++) {
          let y = pos.getY(i) + 0.008;
          if (y > 0.3) y = 0.0;
          pos.setY(i, y);
        }
        pos.needsUpdate = true;
      });
    }
  }

  // ---------------------------------------------------------------------------
  // Exploded / Disassembly Kinematics (Zero-GC 60 FPS Animation)
  // ---------------------------------------------------------------------------
  public applyExplodedOffsets(factor: number) {
    this.currentExplodeFactor = Math.max(0, Math.min(1, factor));
    const t = this.currentExplodeFactor;
    // Cubic smoothstep easing: smooth ramp in, smooth slowdown
    const ease = t * t * (3 - 2 * t);

    // 1. Explode rigid subassemblies
    for (const part of this.explodableParts) {
      part.object.position.x = part.basePosition.x + part.explodeOffset.x * ease;
      part.object.position.y = part.basePosition.y + part.explodeOffset.y * ease;
      part.object.position.z = part.basePosition.z + part.explodeOffset.z * ease;
      if (part.explodeRotation) {
        part.object.rotation.x = part.baseRotation.x + part.explodeRotation.x * ease;
        part.object.rotation.y = part.baseRotation.y + part.explodeRotation.y * ease;
        part.object.rotation.z = part.baseRotation.z + part.explodeRotation.z * ease;
      }
    }

    // 2. Explode internal magnetic core yokes and coil limbs
    if (this.topYoke) {
      this.topYoke.position.y = 0.7 + 0.25 * ease;
    }
    if (this.bottomYoke) {
      this.bottomYoke.position.y = -0.7 - 0.20 * ease;
    }
    for (const item of this.coreLimbs) {
      item.limb.position.x = item.baseLimbPos.x + item.offset.x * ease;
      item.limb.position.z = item.baseLimbPos.z + item.offset.z * ease;
      item.winding.position.x = item.baseWindingPos.x + item.offset.x * ease;
      item.winding.position.z = item.baseWindingPos.z + item.offset.z * ease;
    }

    // 3. Update Anchor points for projected HTML tags & HUD callout
    for (const track of this.anchorTracks) {
      const compRef = this.componentRefs.get(track.id);
      if (compRef) {
        compRef.anchorPoint.x = track.baseAnchor.x + track.explodeOffset.x * ease;
        compRef.anchorPoint.y = track.baseAnchor.y + track.explodeOffset.y * ease;
        compRef.anchorPoint.z = track.baseAnchor.z + track.explodeOffset.z * ease;
      }
    }

    // 4. In realistic mode, reveal internal core and soften tank opacity
    if (this.currentVisualMode === 'realistic') {
      if (this.coreGroup) {
        this.coreGroup.visible = ease > 0.02;
      }
      if (this.tankMesh) {
        const mat = this.tankMesh.material as THREE.MeshStandardMaterial;
        if (ease > 0.04) {
          mat.transparent = true;
          mat.opacity = Math.max(0.42, 1.0 - ease * 0.55);
          mat.depthWrite = ease < 0.2;
        } else {
          mat.transparent = false;
          mat.opacity = 1.0;
          mat.depthWrite = true;
        }
      }
    }
  }

  // ---------------------------------------------------------------------------
  // Visual Mode Switcher (Calm, Technical Colors)
  // ---------------------------------------------------------------------------
  public setVisualMode(mode: VisualMode, telemetry: ModelTelemetry) {
    this.currentVisualMode = mode;
    const topOil = telemetry.topOilTemp ?? 55;
    const isHot = topOil >= 75;
    const isWarm = topOil >= 60;

    // Technical thermal mapping (subdued, not blinding neon)
    const thermalColor = isHot ? 0xa8423f : isWarm ? 0xb57835 : 0x3d6480;

    switch (mode) {
      case 'realistic':
        if (this.coreGroup) this.coreGroup.visible = this.currentExplodeFactor > 0.02;
        if (this.particleGroup) this.particleGroup.visible = false;
        if (this.tankMesh) {
          const mat = this.tankMesh.material as THREE.MeshStandardMaterial;
          if (this.currentExplodeFactor > 0.04) {
            mat.transparent = true;
            mat.opacity = Math.max(0.42, 1.0 - this.currentExplodeFactor * 0.55);
            mat.depthWrite = this.currentExplodeFactor < 0.2;
          } else {
            mat.transparent = false;
            mat.opacity = 1.0;
            mat.depthWrite = true;
          }
          mat.color.setHex(0x64707d); // Authentic utility transformer light gray
          mat.roughness = 0.44;
          mat.metalness = 0.16;
        }
        if (this.tankFlange) {
          const mat = this.tankFlange.material as THREE.MeshStandardMaterial;
          mat.transparent = false;
          mat.opacity = 1.0;
          mat.color.setHex(0x3d4550);
        }
        break;

      case 'thermal':
        if (this.coreGroup) {
          this.coreGroup.visible = true;
          this.coreGroup.traverse((obj) => {
            if (obj instanceof THREE.Mesh && obj.userData?.componentId === 'core') {
              (obj.material as THREE.MeshStandardMaterial).color.setHex(thermalColor);
            }
          });
        }
        if (this.particleGroup) this.particleGroup.visible = false;
        if (this.tankMesh) {
          const mat = this.tankMesh.material as THREE.MeshStandardMaterial;
          mat.transparent = true;
          mat.opacity = 0.6;
          mat.color.setHex(thermalColor);
          mat.roughness = 0.35;
          mat.metalness = 0.2;
        }
        if (this.tankFlange) {
          const mat = this.tankFlange.material as THREE.MeshStandardMaterial;
          mat.color.setHex(thermalColor);
        }
        break;

      case 'xray':
        if (this.coreGroup) this.coreGroup.visible = true;
        if (this.particleGroup) this.particleGroup.visible = false;
        if (this.tankMesh) {
          const mat = this.tankMesh.material as THREE.MeshStandardMaterial;
          mat.transparent = true;
          mat.opacity = 0.18;
          mat.color.setHex(0x525660);
          mat.roughness = 0.25;
          mat.metalness = 0.6;
        }
        if (this.tankFlange) {
          const mat = this.tankFlange.material as THREE.MeshStandardMaterial;
          mat.transparent = true;
          mat.opacity = 0.28;
          mat.color.setHex(0x525660);
        }
        break;

      case 'electrical':
        if (this.coreGroup) this.coreGroup.visible = false;
        if (this.particleGroup) this.particleGroup.visible = true;
        if (this.tankMesh) {
          const mat = this.tankMesh.material as THREE.MeshStandardMaterial;
          mat.transparent = false;
          mat.opacity = 1.0;
          mat.color.setHex(0x36383e);
          mat.roughness = 0.55;
          mat.metalness = 0.28;
        }
        break;
    }
  }

  // ---------------------------------------------------------------------------
  // Component Selection & Restrained Emissive Feedback
  // ---------------------------------------------------------------------------
  public setSelected(id: ComponentId | null) {
    this.selectedComponentId = id;
    this.applyHighlights();
  }

  public setHovered(id: ComponentId | null) {
    this.hoveredComponentId = id;
    this.applyHighlights();
  }

  private applyHighlights() {
    this.interactiveMeshes.forEach((mesh) => {
      const compId = mesh.userData?.componentId as ComponentId;
      const isSelected = this.selectedComponentId === compId;
      const isHovered = this.hoveredComponentId === compId;

      if (mesh.material && 'emissive' in mesh.material) {
        const mat = mesh.material as THREE.MeshStandardMaterial;
        if (isSelected) {
          mat.emissive = new THREE.Color(0xf59e0b); // Warm industrial amber indicator, NOT blue
          mat.emissiveIntensity = 0.3;
        } else if (isHovered) {
          mat.emissive = new THREE.Color(0x71717a); // Subtle neutral graphite lift
          mat.emissiveIntensity = 0.15;
        } else {
          mat.emissive = new THREE.Color(0x000000);
          mat.emissiveIntensity = 0.0;
        }
      }
    });
  }
}
