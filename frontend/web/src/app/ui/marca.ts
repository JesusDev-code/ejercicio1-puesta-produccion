import { ChangeDetectionStrategy, Component, input } from '@angular/core';

@Component({
  selector: 'app-marca',
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <svg aria-hidden="true" [attr.width]="tam()" [attr.height]="tam()" viewBox="0 0 40 40" fill="none">
      <rect x="8" y="8" width="24" height="24" rx="3" transform="rotate(45 20 20)" stroke="#D4AF6E" stroke-width="1.3" />
      <rect x="14" y="14" width="12" height="12" rx="1.5" transform="rotate(45 20 20)" fill="#E01E3C" />
    </svg>
    <span class="textos">
      <span class="nombre">{{ nombre() }}</span>
      <span class="sub">{{ subtitulo() }}</span>
    </span>
  `,
  styles: `
    :host { display: flex; align-items: center; gap: 12px; }
    .textos { display: flex; flex-direction: column; gap: 2px; }
    .nombre { font-family: var(--serif); font-weight: 600; font-size: 26px; line-height: 1; letter-spacing: 0.5px; }
    .sub { font-family: var(--mono); font-size: 10px; letter-spacing: 3px; color: var(--apagado); }
  `,
})
export class Marca {
  readonly tam = input(36);
  readonly nombre = input('Incidentes');
  readonly subtitulo = input('CONSOLA');
}
