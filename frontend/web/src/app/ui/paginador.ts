import { ChangeDetectionStrategy, Component, computed, input, output } from '@angular/core';

import { Opcion, Selector } from './selector';

export interface CambioPagina {
  desplazamiento: number;
  limite: number;
}

/** Paginación con números de página, primera/última y filas por página. */
@Component({
  selector: 'app-paginador',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [Selector],
  template: `
    <nav aria-label="Paginación" class="paginador">
      <span class="resumen">
        @if (total() === 0) { Sin resultados } @else { {{ desde() }}–{{ hasta() }} de {{ total() }} }
      </span>

      @if (paginas() > 1) {
        <div class="paginas">
          <button type="button" class="pag icono" aria-label="Primera página" [disabled]="pagina() === 1" (click)="ir(1)">«</button>
          <button type="button" class="pag icono" aria-label="Página anterior" [disabled]="pagina() === 1" (click)="ir(pagina() - 1)">‹</button>
          @for (n of numeros(); track $index) {
            @if (n === null) {
              <span class="hueco" aria-hidden="true">…</span>
            } @else {
              <button type="button" class="pag" [class.actual]="n === pagina()" [attr.aria-current]="n === pagina() ? 'page' : null"
                [attr.aria-label]="'Página ' + n" (click)="ir(n)">{{ n }}</button>
            }
          }
          <button type="button" class="pag icono" aria-label="Página siguiente" [disabled]="pagina() === paginas()" (click)="ir(pagina() + 1)">›</button>
          <button type="button" class="pag icono" aria-label="Última página" [disabled]="pagina() === paginas()" (click)="ir(paginas())">»</button>
        </div>
      }

      <div class="filas">
        <span aria-hidden="true">Filas</span>
        <app-selector class="selector-filas" [compacto]="true" [opciones]="opcionesLimite()" [valor]="limite()"
          [etiquetaAria]="'Filas por página'" (cambio)="cambiarLimite($event)" />
      </div>
    </nav>
  `,
  styles: `
    .paginador {
      display: flex; flex-wrap: wrap; gap: 14px; align-items: center; justify-content: space-between;
      padding: 14px 24px 22px; font-size: 13px; color: var(--apagado);
    }
    .resumen { font-family: var(--mono); font-size: 12px; min-width: 120px; }
    .paginas { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
    .pag {
      min-width: 40px; height: 40px; padding: 0 10px; border: 0; border-radius: 12px; cursor: pointer;
      background: rgba(255, 255, 255, 0.05); color: var(--texto-2); font-family: var(--mono); font-size: 13px;
      transition: background 0.2s, color 0.2s, box-shadow 0.2s;
    }
    .pag:hover:not(:disabled):not(.actual) { background: rgba(255, 255, 255, 0.1); color: var(--texto); }
    .pag:disabled { opacity: 0.35; cursor: not-allowed; }
    .pag.icono { font-family: var(--sans); font-size: 16px; }
    .pag.actual {
      background: linear-gradient(180deg, #ec2a47, #a80d26); color: #fff4f1; font-weight: 700; cursor: default;
      box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.25), 0 8px 22px -8px rgba(224, 30, 60, 0.8);
    }
    .hueco { padding: 0 4px; color: var(--tenue); }
    .filas { display: flex; align-items: center; gap: 10px; }
    .selector-filas { width: 92px; }
  `,
})
export class Paginador {
  readonly total = input.required<number>();
  readonly limite = input.required<number>();
  readonly desplazamiento = input.required<number>();
  readonly tamanos = input<number[]>([10, 20, 50]);
  readonly cambio = output<CambioPagina>();

  protected readonly pagina = computed(() => Math.floor(this.desplazamiento() / this.limite()) + 1);
  protected readonly paginas = computed(() => Math.max(1, Math.ceil(this.total() / this.limite())));
  protected readonly desde = computed(() => (this.total() ? this.desplazamiento() + 1 : 0));
  protected readonly hasta = computed(() => Math.min(this.total(), this.desplazamiento() + this.limite()));
  protected readonly opcionesLimite = computed<Opcion<number>[]>(() =>
    this.tamanos().map((n) => ({ valor: n, etiqueta: String(n) })),
  );

  /** 1 … 4 5 [6] 7 8 … 20: primera, última y dos a cada lado de la actual. */
  protected readonly numeros = computed<(number | null)[]>(() => {
    const total = this.paginas();
    const actual = this.pagina();
    const visibles = new Set([1, total]);
    for (let n = actual - 2; n <= actual + 2; n++) if (n >= 1 && n <= total) visibles.add(n);
    const orden = [...visibles].sort((a, b) => a - b);
    const salida: (number | null)[] = [];
    orden.forEach((n, i) => {
      if (i > 0 && n - orden[i - 1] > 1) salida.push(null);
      salida.push(n);
    });
    return salida;
  });

  protected ir(pagina: number): void {
    const destino = Math.min(Math.max(1, pagina), this.paginas());
    if (destino === this.pagina()) return;
    this.cambio.emit({ desplazamiento: (destino - 1) * this.limite(), limite: this.limite() });
  }

  protected cambiarLimite(limite: number): void {
    this.cambio.emit({ desplazamiento: 0, limite });
  }
}
