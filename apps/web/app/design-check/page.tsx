"use client";

import {
  Chip,
  Footer,
  GlobalNav,
  PillButton,
  ProvenanceCapsule,
  SearchInput,
  SubNavFrosted,
  Switch,
  Tile,
  UtilityButton,
  UtilityCard,
} from "@/components/ui";

export default function DesignCheckPage() {
  return (
    <div className="min-h-screen bg-[var(--canvas)] pb-12">
      <GlobalNav />
      <SubNavFrosted title="Design QA" action={<PillButton variant="ghost">Preview</PillButton>} />

      <main className="mx-auto flex max-w-[390px] flex-col gap-4 px-4 py-5">
        <Tile tone="dark" className="p-5">
          <p className="text-[12px] uppercase tracking-[0.2em] text-[var(--body-muted)]">State tile</p>
          <h1 className="mt-3 font-[family-name:var(--font-display)] text-[34px] font-semibold leading-[1.1] tracking-0 text-[var(--body-on-dark)]">
            Studying
          </h1>
          <p className="mt-2 text-[17px] leading-[1.47] tracking-[-0.374px] text-[var(--body-muted)]">
            Until 8:00 PM · Calls: No
          </p>
          <div className="mt-4 flex gap-2">
            <PillButton variant="primary">Call</PillButton>
            <PillButton variant="ghost">Message</PillButton>
          </div>
        </Tile>

        <Tile tone="parchment" className="p-4">
          <SearchInput placeholder="What’s happening?" />
          <div className="mt-3 flex flex-wrap gap-2">
            <Chip selected>Studying</Chip>
            <Chip>Free now</Chip>
            <Chip>Going home</Chip>
            <Chip>Phone low</Chip>
          </div>
        </Tile>

        <Tile tone="light" className="p-4">
          <div className="space-y-3">
            <UtilityCard title="Schedule" subtitle="3 meetings today" action={<PillButton variant="ghost">View</PillButton>} />
            <UtilityCard title="Travel" subtitle="Delayed by 12 min" action={<UtilityButton>ETA</UtilityButton>} />
            <UtilityCard title="Permissions" subtitle="Connected + 4 people" action={<Switch checked label="Grant" />} />
          </div>
        </Tile>

        <Tile tone="dark2" className="p-4">
          <p className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px] text-[var(--body-on-dark)]">
            Arrival confirmation is missing
          </p>
          <div className="mt-3 flex gap-2">
            <PillButton variant="primary">Call</PillButton>
            <UtilityButton className="bg-[var(--canvas)] text-[var(--ink)]">Message</UtilityButton>
          </div>
        </Tile>

        <Tile tone="light" className="p-4">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-[14px] leading-[1.29] tracking-[-0.224px] text-[var(--ink-muted-80)]">Pause sharing</span>
              <Switch checked />
            </div>
            <div className="flex items-center justify-between">
              <span className="text-[14px] leading-[1.29] tracking-[-0.224px] text-[var(--ink-muted-80)]">Notify</span>
              <Switch />
            </div>
          </div>
        </Tile>

        <Tile tone="parchment" className="p-4">
          <div className="flex items-center justify-between">
            <span className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px] text-[var(--ink)]">AI-parsed entry</span>
            <ProvenanceCapsule>AI-parsed. Confirm.</ProvenanceCapsule>
          </div>
          <div className="mt-3 space-y-2">
            <p className="text-[14px] leading-[1.43] tracking-[-0.224px] text-[var(--ink-muted-80)]">Resolved time: 6:30 PM · With: Rahul</p>
            <p className="text-[14px] leading-[1.43] tracking-[-0.224px] text-[var(--ink-muted-48)]">Warning: companion still needs confirmation.</p>
          </div>
        </Tile>

        <Footer />
      </main>
    </div>
  );
}
