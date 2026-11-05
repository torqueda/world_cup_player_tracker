import { useMemo, useState } from "react";
import { CountryFlag } from "@/components/country-flag";
import { PlayerLink } from "@/components/player-detail";
import { FilterGroup, SectionHeader, SegmentedControl, SortableTable } from "@/components/ui";
import { ANALYTICS_INPUT } from "@/lib/data/analytics-input";
import { DEFAULT_MEANINGFUL_MINUTES, buildPlayerEfficiencyRows } from "@/lib/analytics";
import { AnalysisPage, sourceNote } from "@/routes/analysis/shared";

export function PlayersRoute() {
  const [efficiencyBucket, setEfficiencyBucket] = useState<"outfield" | "goalkeeper">("outfield");
  const [minMinutes, setMinMinutes] = useState(DEFAULT_MEANINGFUL_MINUTES);
  const efficiencyRows = useMemo(
    () => buildPlayerEfficiencyRows(ANALYTICS_INPUT, minMinutes).filter((row) => row.bucket === efficiencyBucket),
    [minMinutes, efficiencyBucket],
  );

  return (
    <AnalysisPage
      slug="players"
      intro="Goals, assists and cards per 90 minutes, for players with enough minutes for a rate to mean something."
    >
        <section id="efficiency" className="content-panel reveal">
          <SectionHeader
            title="Player efficiency"
            note="Rate rankings exclude zero- and very-low-minute players. Goalkeepers and outfield players are separated because their role context differs."
          />
          <div className="leaders-toolbar">
            <FilterGroup label="Minimum minutes">
              <input
                type="number"
                min={1}
                step={15}
                value={minMinutes}
                onChange={(event) => setMinMinutes(Math.max(1, Number(event.target.value) || DEFAULT_MEANINGFUL_MINUTES))}
              />
            </FilterGroup>
            <SegmentedControl
              ariaLabel="Player role"
              value={efficiencyBucket}
              onChange={setEfficiencyBucket}
              options={[
                { value: "outfield", label: "Outfield" },
                { value: "goalkeeper", label: "Goalkeepers" },
              ]}
            />
          </div>
          <SortableTable
            rows={efficiencyRows.slice(0, 40)}
            getRowKey={(row) => row.playerId}
            initialSortKey="gc90"
            initialSortAsc={false}
            caption="Player efficiency per 90"
            columns={[
              {
                key: "player",
                label: "Player",
                sortValue: (row) => row.playerName,
                render: (row) => <PlayerLink playerId={row.playerId}>{row.playerName}</PlayerLink>,
              },
              {
                key: "team",
                label: "Team",
                sortValue: (row) => row.team,
                render: (row) => (
                  <span className="team-cell">
                    <CountryFlag country={row.team} />
                    {row.team}
                  </span>
                ),
              },
              { key: "minutes", label: "Min", align: "right", initialAsc: false, sortValue: (row) => row.minutes, render: (row) => row.minutes },
              { key: "g90", label: "G/90", align: "right", initialAsc: false, sortValue: (row) => row.goalsPer90, render: (row) => row.goalsPer90.toFixed(2) },
              { key: "a90", label: "A/90", align: "right", initialAsc: false, sortValue: (row) => row.assistsPer90, render: (row) => row.assistsPer90.toFixed(2) },
              { key: "gc90", label: "G+A/90", align: "right", initialAsc: false, sortValue: (row) => row.goalContributionsPer90, render: (row) => row.goalContributionsPer90.toFixed(2) },
              { key: "cards90", label: "Cards/90", align: "right", initialAsc: false, sortValue: (row) => row.cardsPer90, render: (row) => row.cardsPer90.toFixed(2) },
            ]}
          />
          {sourceNote("Per-90 rate = event count / minutes played * 90.", `Players with at least ${minMinutes} minutes in the selected role bucket.`, `${minMinutes} minutes, adjustable by user`)}
        </section>
    </AnalysisPage>
  );
}
