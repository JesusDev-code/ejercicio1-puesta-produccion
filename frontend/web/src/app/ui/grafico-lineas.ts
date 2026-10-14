import { ChangeDetectionStrategy, Component, computed, input, signal } from '@angular/core';

import { Tramo } from '../core/modelos';

interface Punto {
  x: number;
  y: number;
  t: Tramo;
}

/**
 * Serie temporal (eventos por tramo). Una sola serie → sin leyenda; el título la nombra.
 * Área al ~10% + línea de 2px, rejilla hairline, crosshair por X con tooltip. Tabla alternativa
 * accesible oculta tras la figura.
 */
@Component({
  selector: 'app-grafico-lineas',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <figure class="fig">
      <svg
        [attr.viewBox]="'0 0 ' + An + ' ' + Al"
        preserveAspectRatio="none"
        role="img"
        [attr.aria-label]="etiqueta()"
        (pointermove)="mover($event)"
        (pointerleave)="activo.set(-1)"
      >
        <!-- rejilla horizontal: 3 líneas hairline -->
        @for (g of guias(); track g.y) {
          <line class="rejilla" [attr.x1]="pad.i" [attr.x2]="An - pad.d" [attr.y1]="g.y" [attr.y2]="g.y" />
        }
        @if (puntos().length > 1) {
          <path class="area" [attr.d]="areaD()" />
          <path class="linea" [attr.d]="lineaD()" />
        }
        @if (activo() >= 0) {
          <line class="crosshair" [attr.x1]="puntos()[activo()].x" [attr.x2]="puntos()[activo()].x" [attr.y1]="pad.s" [attr.y2]="Al - pad.b" />
          <circle class="punto" [attr.cx]="puntos()[activo()].x" [attr.cy]="puntos()[activo()].y" r="4" />
        }
      </svg>

      @if (activo() >= 0) {
        <div class="tooltip" [style.left.%]="(puntos()[activo()].x / An) * 100">
          <span class="valor">{{ puntos()[activo()].t.total }}</span>
          <span class="momento">{{ etiquetaTramo(puntos()[activo()].t) }}</span>
        </div>
      }

      <figcaption class="eje">
        <span>{{ etiquetaTramo(datos()[0]) }}</span>
        <span>{{ maximo() }} máx.</span>
        <span>{{ etiquetaTramo(datos()[datos().length - 1]) }}</span>
      </figcaption>

      <table class="solo-lector">
        <caption>{{ etiqueta() }}</caption>
        <thead><tr><th>Tramo</th><th>Eventos</th></tr></thead>
        <tbody>
          @for (d of datos(); track d.inicio) {
            <tr><td>{{ etiquetaTramo(d) }}</td><td>{{ d.total }}</td></tr>
          }
        </tbody>
      </table>
    </figure>
  `,
  styles: `
    .fig { position: relative; margin: 0; }
    svg { width: 100%; height: 180px; display: block; overflow: visible; }
    .rejilla { stroke: rgba(255, 255, 255, 0.07); stroke-width: 1; vector-effect: non-scaling-stroke; }
    .area { fill: rgba(224, 30, 60, 0.12); stroke: none; }
    .linea { fill: none; stroke: #ff5a6a; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; vector-effect: non-scaling-stroke; }
    .crosshair { stroke: rgba(255, 90, 106, 0.5); stroke-width: 1; vector-effect: non-scaling-stroke; }
    .punto { fill: #ff5a6a; stroke: #150f14; stroke-width: 2; }
    .eje { display: flex; justify-content: space-between; margin-top: 8px; font-family: var(--mono); font-size: 10px; color: var(--tenue); }
    .tooltip {
      position: absolute; top: 0; transform: translateX(-50%); pointer-events: none;
      display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 6px 10px; border-radius: 10px;
      background: rgba(20, 13, 18, 0.95); box-shadow: 0 8px 24px -8px rgba(0, 0, 0, 0.9), inset 0 0 0 1px rgba(255, 255, 255, 0.08);
      white-space: nowrap;
    }
    .tooltip .valor { font-weight: 700; font-size: 15px; color: var(--texto); }
    .tooltip .momento { font-family: var(--mono); font-size: 10px; color: var(--apagado); }
  `,
})
export class GraficoLineas {
  readonly datos = input.required<Tramo[]>();
  readonly etiqueta = input('Eventos por tramo');
  readonly unidad = input<'minuto' | 'hora'>('minuto');

  protected readonly An = 600;
  protected readonly Al = 180;
  protected readonly pad = { i: 4, d: 4, s: 12, b: 4 };
  protected readonly activo = signal(-1);

  protected readonly maximo = computed(() => Math.max(1, ...this.datos().map((d) => d.total)));

  protected readonly puntos = computed<Punto[]>(() => {
    const d = this.datos();
    if (d.length < 2) return [];
    const ancho = this.An - this.pad.i - this.pad.d;
    const alto = this.Al - this.pad.s - this.pad.b;
    const max = this.maximo();
    return d.map((t, i) => ({
      x: this.pad.i + (ancho * i) / (d.length - 1),
      y: this.pad.s + alto * (1 - t.total / max),
      t,
    }));
  });

  protected readonly guias = computed(() => {
    const alto = this.Al - this.pad.s - this.pad.b;
    return [0, 0.5, 1].map((f) => ({ y: this.pad.s + alto * f }));
  });

  protected readonly lineaD = computed(() =>
    this.puntos()
      .map((p, i) => `${i ? 'L' : 'M'}${p.x.toFixed(1)},${p.y.toFixed(1)}`)
      .join(' '),
  );

  protected readonly areaD = computed(() => {
    const p = this.puntos();
    if (!p.length) return '';
    const base = this.Al - this.pad.b;
    return `${this.lineaD()} L${p[p.length - 1].x.toFixed(1)},${base} L${p[0].x.toFixed(1)},${base} Z`;
  });

  protected mover(ev: PointerEvent): void {
    const svg = ev.currentTarget as SVGSVGElement;
    const caja = svg.getBoundingClientRect();
    const frac = (ev.clientX - caja.left) / caja.width;
    const i = Math.round(frac * (this.datos().length - 1));
    this.activo.set(Math.min(Math.max(0, i), this.datos().length - 1));
  }

  protected etiquetaTramo(t: Tramo | undefined): string {
    if (!t) return '';
    const f = new Date(t.inicio);
    return this.unidad() === 'minuto'
      ? f.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' })
      : f.toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit' });
  }
}
