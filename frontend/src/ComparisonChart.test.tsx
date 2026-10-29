import '@testing-library/jest-dom/vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import ComparisonChart from './ComparisonChart';
afterEach(cleanup);
it('handles absent observations without invalid chart coordinates',()=>{
 render(<ComparisonChart points={[]} symbol="TCS"/>);
 expect(screen.getByText('NO DATA')).toBeVisible();
 expect(screen.queryByRole('img')).not.toBeInTheDocument();
});
it('moves the readout through observations using the keyboard',()=>{
 render(<ComparisonChart symbol="TCS" points={[{trade_date:'2026-10-27',stock_index:100,benchmark_index:100},{trade_date:'2026-10-28',stock_index:102,benchmark_index:101}]}/>);
 expect(screen.getByText('2026-10-28 / TCS 102.00 / Peers 101.00')).toBeVisible();
 fireEvent.keyDown(screen.getByRole('img'),{key:'ArrowLeft'});
 expect(screen.getByText('2026-10-27 / TCS 100.00 / Peers 100.00')).toBeVisible();
 fireEvent.keyDown(screen.getByRole('img'),{key:'ArrowLeft'});
 expect(screen.getByText('2026-10-27 / TCS 100.00 / Peers 100.00')).toBeVisible();
});
