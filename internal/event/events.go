package event

import (
    "math/rand"
    "time"
)

func init() {
    rand.Seed(time.Now().UnixNano())
}

type ScheduledEventBuilder struct {
    bus *Bus
}

func NewScheduledEventBuilder(bus *Bus) *ScheduledEventBuilder {
    return &ScheduledEventBuilder{bus: bus}
}

func (b *ScheduledEventBuilder) ScheduleWeatherChange(tick int64, weather string, location string) {
    b.bus.Schedule(&Event{Tick: tick, Type: WeatherChange, Location: location, Payload: map[string]interface{}{"weather": weather}}, tick)
}

func (b *ScheduledEventBuilder) ScheduleResourceFound(tick int64, resource string, amount int, location string, agentID string) {
    b.bus.Schedule(&Event{Tick: tick, Type: ResourceFound, Location: location, Payload: map[string]interface{}{"resource": resource, "amount": amount, "agent_id": agentID}}, tick)
}

func (b *ScheduledEventBuilder) ScheduleSocialEncounter(tick int64, location string, agentIDs []string) {
    b.bus.Schedule(&Event{Tick: tick, Type: SocialEncounter, Location: location, Payload: map[string]interface{}{"agents": agentIDs}}, tick)
}

func (b *ScheduledEventBuilder) ScheduleItemCrafted(tick int64, item string, agentID string) {
    b.bus.Schedule(&Event{Tick: tick, Type: ItemCrafted, Location: "workshop", Payload: map[string]interface{}{"item": item, "agent_id": agentID}}, tick)
}

func (b *ScheduledEventBuilder) ScheduleRumorSpread(tick int64, claim string, fromAgent string, toAgent string) {
    b.bus.Schedule(&Event{Tick: tick, Type: RumorSpread, Location: "square", Payload: map[string]interface{}{"claim": claim, "from": fromAgent, "to": toAgent}}, tick)
}

func (b *ScheduledEventBuilder) GenerateDailySchedule(day int64, agentIDs []string) {
    baseTick := (day - 1) * 24
    weathers := []string{"clear", "cloudy", "rainy"}
    b.ScheduleWeatherChange(baseTick+6, weathers[rand.Intn(3)], "square")
    if rand.Float64() < 0.7 {
        resources := []string{"wood", "stone", "food", "metal"}
        agent := agentIDs[rand.Intn(len(agentIDs))]
        b.ScheduleResourceFound(baseTick+10, resources[rand.Intn(4)], rand.Intn(3)+1, "wilderness", agent)
    }
    if len(agentIDs) >= 2 {
        a1 := agentIDs[rand.Intn(len(agentIDs))]
        a2 := agentIDs[rand.Intn(len(agentIDs))]
        b.ScheduleSocialEncounter(baseTick+12, "square", []string{a1, a2})
    }
    if rand.Float64() < 0.5 {
        items := []string{"tool", "furniture", "weapon"}
        agent := agentIDs[rand.Intn(len(agentIDs))]
        b.ScheduleItemCrafted(baseTick+15, items[rand.Intn(3)], agent)
    }
    if rand.Float64() < 0.4 {
        claims := []string{"strange sounds", "missing supplies", "new discovery"}
        from := agentIDs[rand.Intn(len(agentIDs))]
        to := agentIDs[rand.Intn(len(agentIDs))]
        b.ScheduleRumorSpread(baseTick+18, claims[rand.Intn(3)], from, to)
    }
}