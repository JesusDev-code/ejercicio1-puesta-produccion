import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

export interface Barra {
  etiqueta: string;
  valor: number;
  /** Clase de color opcional (severidad, tipo…). Por defecto, carmesí. */
  clase?: string;
}

/**
 * Barras horizontales ordenadas de mayor a menor. Categorías nominales → un solo color
 * (identidad por la etiqueta, no por el valor). Etiqueta y valor directos; la longitud es el dato.
 * Va en HTML plano (no SVG): el texto fluye y nunca se recorta.
 */
@Component({
  selector: 'app-grafico-barras',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <ul class="barras" [attr.aria-label]="etiqueta()">
      @for (b of filas(); track b.etiqueta) {
        <li class="fila">
          <span class="nombre" [title]="b.etiqueta">{{ b.etiqueta }}</span>
          <span class="pista">
            <span class="relleno" [class]="b.clase ?? 'c-sangre'" [style.width.%]="ancho(b.valor)"></span>
          </span>
          <span class="valor">{{ b.valor }}</span>
        </li>
      } @empty {
        <li class="vacio">Sin datos en el periodo.</li>
      }
    </ul>
  `,
  styles: `
    .barras { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
    .fila { display: grid; grid-template-columns: minmax(96px, 34%) 1fr auto; align-items: center; gap: 12px; }
    .nombre { font-size: 13px; color: var(--texto-2); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .pista { height: 10px; border-radius: 999px; background: rgba(255, 255, 255, 0.05); overflow: hidden; }
    .relleno { display: block; height: 100%; border-radius: 999px; min-width: 3px; transition: width 0.4s ease; }
    .c-sangre { background: linear-gradient(90deg, #a8203a, #ff5a6a); }
    .c-baja { background: #b8a5ab; }
    .c-media { background: #f0c987; }
    .c-alta { background: #ff9a5c; }
    .c-critica { background: linear-gradient(90deg, #a8203a, #ff4d5e); }
    .valor { font-family: var(--mono); font-size: 13px; color: var(--texto); font-variant-numeric: tabular-nums; min-width: 2ch; text-align: right; }
    .vacio { color: var(--apagado); font-size: 14px; }
  `,
})
export class GraficoBarras {
  readonly datos = input.required<Barra[]>();
  readonly etiqueta = input('');
  readonly maximoFilas = input(10);

  protected readonly filas = computed(() =>
    [...this.datos()].sort((a, b) => b.valor - a.valor).slice(0, this.maximoFilas()),
  );
  private readonly max = computed(() => Math.max(1, ...this.datos().map((d) => d.valor)));

  protected ancho(valor: number): number {
    return (valor / this.max()) * 100;
  }
}
