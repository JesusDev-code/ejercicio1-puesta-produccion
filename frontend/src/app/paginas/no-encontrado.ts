import { ChangeDetectionStrategy, Component } from '@angular/core';

import { NoExiste } from '../ui/estados';

@Component({
  selector: 'app-no-encontrado',
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [NoExiste],
  template: '<app-no-existe titulo="Esta página no existe" />',
})
export class NoEncontrado {}
