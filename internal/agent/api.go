package agent

func (a *Agent) ToMap() map[string]interface{} {
    return map[string]interface{}{
        "id":       a.Identity.ID,
        "name":     a.Identity.Name,
        "role":     string(a.Identity.Role),
        "traits":   a.Identity.Traits,
        "energy":   a.State.Energy,
        "mood":     string(a.State.Mood),
        "gold":     a.State.Gold,
        "location": a.State.Location,
        "task":     a.TaskSummary(),
        "skills":   a.Identity.Skills,
    }
}

func (a *Agent) TaskSummary() string {
    if a.State.CurrentTask != nil {
        return a.State.CurrentTask.Description
    }
    return "idle"
}

func (a *Agent) CurrentGoal() string {
    if len(a.Goals) > 0 {
        return a.Goals[0].Description
    }
    return ""
}

func (a *Agent) Subscribe(bus interface{}) {
    // Subscription handled by tick engine
}