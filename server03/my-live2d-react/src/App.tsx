// App.tsx
import { useEffect, useRef } from 'react';
import * as PIXI from 'pixi.js';
import { Live2DModel } from 'pixi-live2d-display';

declare global {
  interface Window { PIXI: typeof PIXI }
}
window.PIXI = PIXI;

export default function App() {
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    // ✅ Deja que Pixi cree su propio canvas
    const app = new PIXI.Application({
      resizeTo: window,
      backgroundAlpha: 0,
      antialias: true,
    });

    // Inserta el canvas generado en el contenedor
    containerRef.current.appendChild(app.view as HTMLCanvasElement);

    let disposed = false;

    (async () => {
      const model = await Live2DModel.from('models/Haru/Haru.model3.json');
      if (disposed) return;

      app.stage.addChild(model);

      // transforms
      model.x = 100;
      model.y = 100;
      model.rotation = Math.PI;
      model.skew.x = Math.PI;
      model.scale.set(2, 2);
      model.anchor.set(0.5, 0.5);

      // interaction
      model.on('hit', (hitAreas) => {
        if (hitAreas.includes('body')) {
          model.motion('tap_body');
        }
      });
    })();

    // cleanup al desmontar
    return () => {
      disposed = true;
      app.destroy(true, { children: true, texture: true, baseTexture: true });
    };
  }, []);

  return (
    <div
      ref={containerRef}
      style={{ width: '100vw', height: '100vh' }}
    />
  );
}
