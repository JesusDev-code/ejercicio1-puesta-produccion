import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';

import { ESTADOS, Estado, SEVERIDADES, Severidad } from '../core/modelos';

@Component({
  selector: 'app-severidad',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="sev" [class]="info().clase"><span class="punto"></span>{{ info().nombre }}</span>`,
  styles: `
    .sev { display: inline-flex; align-items: center; gap: 8px; font-weight: 600; font-size: 13px; white-space: nowrap; }
    .sev-baja { color: #b8a5ab; }
    .sev-media { color: #f0c987; }
    .sev-alta { color: #ff9a5c; }
    .sev-critica { color: #ff4d5e; }
  `,
})
export class PildoraSeveridad {
  readonly valor = input.required<Severidad>();
  protected readonly info = computed(() => SEVERIDADES[this.valor()]);
}

@Component({
  selector: 'app-estado',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `<span class="pildora" [class]="info().clase">{{ info().nombre }}</span>`,
  styles: `
    .pildora { display: inline-block; padding: 5px 12px; border-radius: 999px; font-size: 12px; font-weight: 700; white-space: nowrap; }
    .est-abierto { color: #f1e6e0; background: rgba(241, 230, 224, 0.1); }
    .est-analisis { color: #f0c987; background: rgba(212, 175, 110, 0.16); }
    .est-resuelto { color: #8fd3b8; background: rgba(143, 211, 184, 0.13); }
    .est-cerrado { color: #a8939a; background: rgba(168, 147, 154, 0.12); }
  `,
})
export class PildoraEstado {
  readonly valor = input.required<Estado>();
  protected readonly info = computed(() => ESTADOS[this.valor()]);
}
