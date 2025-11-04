import { ReactNode } from 'react'

type TabOption = {
  id: string
  label: ReactNode
}

type TabsProps = {
  tabs: TabOption[]
  active: string
  onChange?: (id: string) => void
}

export function Tabs({ tabs, active, onChange }: TabsProps) {
  return (
    <nav className="tabs" aria-label="Secciones">
      {tabs.map((tab) => (
        <button
          key={tab.id}
          type="button"
          className={`tab ${tab.id === active ? 'tab--active' : ''}`}
          onClick={() => onChange?.(tab.id)}
          aria-pressed={tab.id === active}
        >
          {tab.label}
        </button>
      ))}
    </nav>
  )
}

export type SegmentOption = {
  value: string
  label: ReactNode
}

type SegmentedControlProps = {
  options: SegmentOption[]
  value: string
  onChange?: (value: string) => void
}

export function SegmentedControl({ options, value, onChange }: SegmentedControlProps) {
  return (
    <div className="segmented" role="radiogroup">
      {options.map((option) => {
        const isActive = option.value === value
        return (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={isActive}
            className={`segment ${isActive ? 'segment--active' : ''}`}
            onClick={() => onChange?.(option.value)}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
