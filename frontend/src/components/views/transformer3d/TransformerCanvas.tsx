import React, { useEffect, useRef, useCallback } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import {
  ComponentId,
  VisualMode,
  ModelTelemetry,
  TransformerSceneBuilder,
} from './TransformerGeometry';
import { X } from 'lucide-react';

export interface ComponentTagItem {
  id: ComponentId;
  name: string;
  badgeLabel: string;
  status: 'NORMAL' | 'WATCH' | 'WARNING' | 'CRITICAL' | 'UNAVAILABLE';
  primaryValue: string;
  secondaryValue: string;
  category: string;
  targetTab?: string;
  targetTabLabel?: string;
}

interface TransformerCanvasProps {
  telemetry: ModelTelemetry;
  selectedId: ComponentId | null;
  hoveredId: ComponentId | null;
  onSelectComponent: (id: ComponentId | null) => void;
  onHoverComponent: (id: ComponentId | null) => void;
  visualMode: VisualMode;
  isAutoRotate: boolean;
  cameraPresetTrigger?: string;
  className?: string;
  showTags?: boolean;
  componentsMeta?: Record<ComponentId, ComponentTagItem>;
  onNavigateTab?: (tab: string) => void;
  explodeProgress?: number;
}

export const TransformerCanvas: React.FC<TransformerCanvasProps> = ({
  telemetry,
  selectedId,
  hoveredId,
  onSelectComponent,
  onHoverComponent,
  visualMode,
  isAutoRotate,
  cameraPresetTrigger,
  className,
  showTags = true,
  componentsMeta,
  onNavigateTab,
  explodeProgress = 0,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  // Three.js internal references
  const sceneRef = useRef<THREE.Scene | null>(null);
  const cameraRef = useRef<THREE.PerspectiveCamera | null>(null);
  const rendererRef = useRef<THREE.WebGLRenderer | null>(null);
  const controlsRef = useRef<OrbitControls | null>(null);
  const builderRef = useRef<TransformerSceneBuilder | null>(null);
  const animFrameIdRef = useRef<number | null>(null);

  // Overlay elements refs for zero-lag 60fps tracking
  const tagElementsRef = useRef<Map<ComponentId, HTMLDivElement>>(new Map());
  const calloutElementRef = useRef<HTMLDivElement>(null);

  // Sync ref for event handlers to avoid stale closures
  const selectedIdRef = useRef<ComponentId | null>(selectedId);
  useEffect(() => {
    selectedIdRef.current = selectedId;
  }, [selectedId]);

  const showTagsRef = useRef<boolean>(showTags);
  useEffect(() => {
    showTagsRef.current = showTags;
  }, [showTags]);

  const explodeProgressRef = useRef<number>(explodeProgress);
  useEffect(() => {
    explodeProgressRef.current = explodeProgress;
  }, [explodeProgress]);

  const currentExplodeRef = useRef<number>(0);

  // Camera animation target
  const targetCameraPos = useRef<THREE.Vector3 | null>(null);
  const targetLookAt = useRef<THREE.Vector3 | null>(null);

  // ---------------------------------------------------------------------------
  // Initialize Three.js Scene
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (!containerRef.current || !canvasRef.current) return;

    const width = containerRef.current.clientWidth || 700;
    const height = containerRef.current.clientHeight || 480;

    // 1. Scene
    const scene = new THREE.Scene();
    sceneRef.current = scene;

    // 2. Camera: Balanced, generous framing so the entire model and exploded parts are comfortably in frame
    const camera = new THREE.PerspectiveCamera(35, width / height, 0.1, 100);
    camera.position.set(10.5, 6.5, 10.5);
    cameraRef.current = camera;

    // 3. Renderer with High-DPI and ACES Filmic Tone Mapping
    const renderer = new THREE.WebGLRenderer({
      canvas: canvasRef.current,
      antialias: true,
      alpha: true,
      powerPreference: 'high-performance',
    });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.12;
    rendererRef.current = renderer;

    // 4. OrbitControls: Smooth damping, polar angle locked to ground
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.06;
    controls.maxPolarAngle = Math.PI / 2 + 0.02; // Prevent looking under ground
    controls.minDistance = 4.0;
    controls.maxDistance = 30.0;
    controls.target.set(0, 0.35, 0);
    controlsRef.current = controls;

    // 5. Coherent Multi-Point Industrial Studio Lighting (Balanced Substation Utility Lighting)
    const hemiLight = new THREE.HemisphereLight(0xf0f4fa, 0x22262d, 1.05);
    hemiLight.position.set(0, 16, 0);
    scene.add(hemiLight);

    const keyLight = new THREE.DirectionalLight(0xfffbf2, 1.95);
    keyLight.position.set(9, 14, 9);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.width = 2048;
    keyLight.shadow.mapSize.height = 2048;
    keyLight.shadow.camera.near = 0.5;
    keyLight.shadow.camera.far = 32;
    keyLight.shadow.camera.left = -6.0;
    keyLight.shadow.camera.right = 6.0;
    keyLight.shadow.camera.top = 6.0;
    keyLight.shadow.camera.bottom = -6.0;
    keyLight.shadow.bias = -0.0003;
    scene.add(keyLight);

    const fillLight = new THREE.DirectionalLight(0xdbe3ee, 0.95);
    fillLight.position.set(-9, 8, -6);
    scene.add(fillLight);

    const rimLight = new THREE.DirectionalLight(0xedf2f8, 0.85);
    rimLight.position.set(0, 7, -10);
    scene.add(rimLight);

    const frontLight = new THREE.DirectionalLight(0xf7f8fa, 0.75);
    frontLight.position.set(0, 3, 8.5);
    scene.add(frontLight);

    const bounceLight = new THREE.DirectionalLight(0x2a3038, 0.6);
    bounceLight.position.set(0, -6, 0);
    scene.add(bounceLight);

    // 6. Build Transformer Model
    const builder = new TransformerSceneBuilder();
    builderRef.current = builder;
    scene.add(builder.rootGroup);

    // 7. Touch & Click Raycaster with Drag-Threshold Filter
    const raycaster = new THREE.Raycaster();
    const pointer = new THREE.Vector2();
    let pointerDownPos: { x: number; y: number; time: number } | null = null;

    const handlePointerDown = (e: PointerEvent) => {
      pointerDownPos = { x: e.clientX, y: e.clientY, time: performance.now() };
    };

    const handlePointerUp = (e: PointerEvent) => {
      if (!pointerDownPos) return;
      const dx = e.clientX - pointerDownPos.x;
      const dy = e.clientY - pointerDownPos.y;
      const dist = Math.hypot(dx, dy);
      const duration = performance.now() - pointerDownPos.time;
      pointerDownPos = null;

      // Only trigger toggle selection if movement was small (< 8px) and quick (< 450ms)
      // This strictly separates deliberate tap/clicks from OrbitControls camera drags
      if (dist < 8 && duration < 450) {
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(pointer, camera);
        const intersects = raycaster.intersectObjects(builder.interactiveMeshes, true);
        if (intersects.length > 0) {
          const compId = intersects[0].object.userData?.componentId as ComponentId;
          if (compId) {
            // Touch toggle: tap the same component to deselect, tap another to select
            onSelectComponent(selectedIdRef.current === compId ? null : compId);
          }
        } else {
          // Tap on empty background clears active selection
          onSelectComponent(null);
        }
      }
    };

    const handlePointerMove = (e: PointerEvent) => {
      // For mouse pointers, update hover highlight and cursor
      if (e.pointerType === 'mouse') {
        const rect = renderer.domElement.getBoundingClientRect();
        pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
        pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

        raycaster.setFromCamera(pointer, camera);
        const intersects = raycaster.intersectObjects(builder.interactiveMeshes, true);
        if (intersects.length > 0) {
          const compId = intersects[0].object.userData?.componentId as ComponentId;
          builder.setHovered(compId);
          onHoverComponent(compId);
          renderer.domElement.style.cursor = 'pointer';
        } else {
          builder.setHovered(null);
          onHoverComponent(null);
          renderer.domElement.style.cursor = 'grab';
        }
      }
    };

    const domElement = renderer.domElement;
    domElement.addEventListener('pointerdown', handlePointerDown);
    domElement.addEventListener('pointerup', handlePointerUp);
    domElement.addEventListener('pointermove', handlePointerMove);

    // 8. 60 FPS Render Loop & Projected Screen Overlay Tracking
    const tempVec = new THREE.Vector3();

    const animate = () => {
      animFrameIdRef.current = requestAnimationFrame(animate);

      // Smooth camera interpolation
      if (targetCameraPos.current && targetLookAt.current) {
        camera.position.lerp(targetCameraPos.current, 0.09);
        controls.target.lerp(targetLookAt.current, 0.09);

        if (camera.position.distanceTo(targetCameraPos.current) < 0.03) {
          targetCameraPos.current = null;
          targetLookAt.current = null;
        }
      }

      controls.autoRotate = isAutoRotate;
      controls.autoRotateSpeed = 0.8;
      controls.update();

      // Organic animated disassembly / exploded view kinematics interpolation
      const targetExplode = explodeProgressRef.current;
      const explodeDiff = targetExplode - currentExplodeRef.current;
      if (Math.abs(explodeDiff) > 0.0008) {
        currentExplodeRef.current += explodeDiff * 0.085;
        builder.applyExplodedOffsets(currentExplodeRef.current);
      } else if (currentExplodeRef.current !== targetExplode) {
        currentExplodeRef.current = targetExplode;
        builder.applyExplodedOffsets(currentExplodeRef.current);
      }

      builder.updateTelemetry(telemetry);
      renderer.render(scene, camera);

      // -----------------------------------------------------------------------
      // Screen Projection for Value Tags (Zero React re-renders)
      // -----------------------------------------------------------------------
      const w = domElement.clientWidth;
      const h = domElement.clientHeight;

      if (w > 0 && h > 0) {
        // A. Update Value Tags positions
        const shouldShowTags = showTagsRef.current;
        for (const [id, compRef] of builder.componentRefs.entries()) {
          const el = tagElementsRef.current.get(id);
          if (!el) continue;

          if (!shouldShowTags) {
            el.style.display = 'none';
            continue;
          }

          tempVec.copy(compRef.anchorPoint);
          tempVec.project(camera);

          const isBehind = tempVec.z >= 1.0;
          const sx = ((tempVec.x + 1) / 2) * w;
          const sy = ((-tempVec.y + 1) / 2) * h;
          const inBounds = sx >= 15 && sx <= w - 15 && sy >= 20 && sy <= h - 15;

          if (!isBehind && inBounds) {
            el.style.display = 'flex';
            el.style.transform = `translate3d(${Math.round(sx)}px, ${Math.round(sy)}px, 0) translate(-50%, -100%)`;
          } else {
            el.style.display = 'none';
          }
        }

        // B. Update Active Component HUD Callout position
        const activeSelId = selectedIdRef.current;
        const calloutEl = calloutElementRef.current;
        if (calloutEl) {
          if (activeSelId && builder.componentRefs.has(activeSelId)) {
            const compRef = builder.componentRefs.get(activeSelId)!;
            tempVec.copy(compRef.anchorPoint);
            tempVec.project(camera);

            const isBehind = tempVec.z >= 1.0;
            const sx = ((tempVec.x + 1) / 2) * w;
            const sy = ((-tempVec.y + 1) / 2) * h;

            if (!isBehind) {
              calloutEl.style.display = 'block';
              // Clamp so micro-callout stays comfortably inside the canvas boundaries
              const clampedX = Math.max(90, Math.min(w - 90, sx));
              const clampedY = Math.max(25, Math.min(h - 25, sy - 20));
              calloutEl.style.transform = `translate3d(${Math.round(clampedX)}px, ${Math.round(clampedY)}px, 0) translate(-50%, -100%)`;
            } else {
              calloutEl.style.display = 'none';
            }
          } else {
            calloutEl.style.display = 'none';
          }
        }
      }
    };
    animate();

    // 9. ResizeObserver
    const resizeObserver = new ResizeObserver((entries) => {
      for (let entry of entries) {
        const { width: nw, height: nh } = entry.contentRect;
        if (nw > 0 && nh > 0) {
          camera.aspect = nw / nh;
          camera.updateProjectionMatrix();
          renderer.setSize(nw, nh);
        }
      }
    });
    resizeObserver.observe(containerRef.current);

    return () => {
      if (animFrameIdRef.current) cancelAnimationFrame(animFrameIdRef.current);
      resizeObserver.disconnect();
      domElement.removeEventListener('pointerdown', handlePointerDown);
      domElement.removeEventListener('pointerup', handlePointerUp);
      domElement.removeEventListener('pointermove', handlePointerMove);
      renderer.dispose();
    };
  }, []);

  // ---------------------------------------------------------------------------
  // Synchronize Visual Mode & Telemetry
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (builderRef.current) {
      builderRef.current.setVisualMode(visualMode, telemetry);
    }
  }, [visualMode, telemetry]);

  // ---------------------------------------------------------------------------
  // Synchronize Component Highlight & Hover
  // ---------------------------------------------------------------------------
  useEffect(() => {
    if (builderRef.current) {
      builderRef.current.setSelected(selectedId);
    }
  }, [selectedId]);

  useEffect(() => {
    if (builderRef.current) {
      builderRef.current.setHovered(hoveredId);
    }
  }, [hoveredId]);

  // ---------------------------------------------------------------------------
  // Camera Presets Dispatcher (Clean framing, balanced distance)
  // ---------------------------------------------------------------------------
  const applyPreset = useCallback((preset: string) => {
    switch (preset) {
      case 'isometric':
        targetCameraPos.current = new THREE.Vector3(10.5, 6.5, 10.5);
        targetLookAt.current = new THREE.Vector3(0, 0.35, 0);
        break;
      case 'top_bushings':
        targetCameraPos.current = new THREE.Vector3(0, 5.2, 3.8);
        targetLookAt.current = new THREE.Vector3(0, 1.35, 0.2);
        break;
      case 'front_tank':
        targetCameraPos.current = new THREE.Vector3(0, 1.4, 6.8);
        targetLookAt.current = new THREE.Vector3(0, 0.35, 0);
        break;
      case 'radiators':
        targetCameraPos.current = new THREE.Vector3(-6.2, 2.2, 3.8);
        targetLookAt.current = new THREE.Vector3(-1.4, 0.30, 0);
        break;
      case 'conservator':
        targetCameraPos.current = new THREE.Vector3(4.2, 3.6, -3.0);
        targetLookAt.current = new THREE.Vector3(0.35, 1.8, -0.65);
        break;
    }
  }, []);

  useEffect(() => {
    if (cameraPresetTrigger) {
      applyPreset(cameraPresetTrigger);
    }
  }, [cameraPresetTrigger, applyPreset]);

  // Helper for tag metadata
  const activeMeta = selectedId && componentsMeta ? componentsMeta[selectedId] : null;

  return (
    <div
      ref={containerRef}
      style={{
        background: 'radial-gradient(circle at 50% 36%, #212328 0%, #151619 60%, #0d0e10 100%)',
      }}
      className={
        className ||
        'relative w-full h-[480px] sm:h-[500px] lg:h-[520px] rounded-2xl border border-line/60 overflow-hidden select-none shadow-xl'
      }
    >
      {/* 3D WebGL Canvas */}
      <canvas ref={canvasRef} className="w-full h-full block outline-none cursor-grab" />

      {/* --------------------------------------------------------------------- */}
      {/* Interactive Value Tags (Projected live in 3D, Touch Toggleable)       */}
      {/* --------------------------------------------------------------------- */}
      {componentsMeta &&
        (Object.keys(componentsMeta) as ComponentId[]).map((id) => {
          const comp = componentsMeta[id];
          const isSelected = selectedId === id;
          const isHovered = hoveredId === id;

          const dotColor =
            comp.status === 'NORMAL'
              ? 'bg-ok'
              : comp.status === 'WATCH'
              ? 'bg-accent'
              : comp.status === 'WARNING'
              ? 'bg-warn'
              : comp.status === 'CRITICAL'
              ? 'bg-crit'
              : 'bg-muted';

          return (
            <div
              key={id}
              ref={(el) => {
                if (el) tagElementsRef.current.set(id, el);
                else tagElementsRef.current.delete(id);
              }}
              onClick={(e) => {
                e.stopPropagation();
                onSelectComponent(selectedId === id ? null : id);
              }}
              className={`absolute top-0 left-0 pointer-events-auto cursor-pointer transition-all duration-150 select-none ${
                isSelected
                  ? 'bg-surface-3/95 border-accent text-ink ring-2 ring-accent/40 shadow-lg scale-105 z-20'
                  : isHovered
                  ? 'bg-surface-2/95 border-line-strong text-ink shadow-md scale-105 z-10'
                  : 'bg-surface/90 border-line/80 text-ink-2 hover:border-accent/80 hover:text-ink shadow-sm'
              } backdrop-blur-md px-2 py-1 rounded-md border flex items-center gap-1.5`}
              style={{ display: 'none', willChange: 'transform' }}
              title={`Tap to inspect ${comp.name}`}
            >
              <span className={`w-1.5 h-1.5 rounded-full ${dotColor}`} />
              <span className="text-[10px] font-mono font-bold text-muted">{comp.badgeLabel}</span>
              <span className="text-[11px] font-mono font-semibold text-ink num">{comp.primaryValue}</span>
            </div>
          );
        })}

      {/* --------------------------------------------------------------------- */}
      {/* Active Component Sleek Micro-Callout (Low-Profile, Zero Clutter)      */}
      {/* --------------------------------------------------------------------- */}
      <div
        ref={calloutElementRef}
        className="absolute top-0 left-0 pointer-events-auto select-none bg-canvas/92 border border-line-strong/80 rounded-lg shadow-xl backdrop-blur-xl px-2.5 py-1.5 flex items-center gap-2 z-30 transition-all text-xs"
        style={{ display: 'none', willChange: 'transform' }}
      >
        {activeMeta && (
          <div className="flex items-center gap-2">
            <span
              className={`w-2 h-2 rounded-full shrink-0 ${
                activeMeta.status === 'NORMAL'
                  ? 'bg-ok'
                  : activeMeta.status === 'WATCH'
                  ? 'bg-accent'
                  : activeMeta.status === 'WARNING'
                  ? 'bg-warn'
                  : 'bg-crit'
              }`}
            />
            <span className="font-semibold text-ink text-[11.5px] whitespace-nowrap">
              {activeMeta.name}
            </span>
            <span className="text-muted/40 font-light">|</span>
            <span className="font-mono text-accent font-bold text-[11px] whitespace-nowrap num">
              {activeMeta.primaryValue}
            </span>
            {onNavigateTab && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onNavigateTab(activeMeta.targetTab || 'evidence');
                }}
                className="hover:text-accent text-muted/70 text-[10.5px] font-medium flex items-center gap-0.5 px-1 py-0.5 rounded hover:bg-surface-3 transition-colors ml-0.5"
                title={`Open ${activeMeta.targetTabLabel || 'Evidence'}`}
              >
                <span>{activeMeta.targetTabLabel || 'details'}</span>
                <span className="text-[10px]">&rarr;</span>
              </button>
            )}
            <button
              onClick={(e) => {
                e.stopPropagation();
                onSelectComponent(null);
              }}
              className="w-4 h-4 rounded hover:bg-surface-3 flex items-center justify-center text-muted hover:text-ink transition-colors ml-0.5"
              title="Dismiss callout"
            >
              <X className="w-3 h-3" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
};
