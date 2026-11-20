import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { StatusBadge } from '../components/StatusBadge';
import { KpiCard } from '../components/KpiCard';
import { Layers } from 'lucide-react';

describe('StatusBadge Component', () => {
  it('renders completed status badge correctly', () => {
    render(<StatusBadge status="completed" />);
    expect(screen.getByText('completed')).toBeInTheDocument();
  });

  it('renders critical risk tier badge correctly', () => {
    render(<StatusBadge status="🔴 Critical" />);
    expect(screen.getByText('🔴 Critical')).toBeInTheDocument();
  });
});

describe('KpiCard Component', () => {
  it('renders metric title and value', () => {
    render(
      <KpiCard
        title="Total LOC"
        value="12,500"
        subtitle="Python LOC"
        icon={<Layers data-testid="kpi-icon" />}
        badge={{ text: 'Healthy', variant: 'positive' }}
      />
    );

    expect(screen.getByText('Total LOC')).toBeInTheDocument();
    expect(screen.getByText('12,500')).toBeInTheDocument();
    expect(screen.getByText('Python LOC')).toBeInTheDocument();
    expect(screen.getByText('Healthy')).toBeInTheDocument();
  });
});
