package agent

// PopulateAgents creates the 10 initial agents defined in world-v0.1.md
func PopulateAgents() []*Agent {
	agents := []*Agent{}

	// 1. Elder
	elder := NewAgent(
		NewIdentity("agent_elder", "Grandmother Mae", RoleElder),
		NewDefaultSchedule(),
	)
	elder.Identity.Traits = []string{"wise", "social", "patient"}
	elder.Identity.Skills[SkillName("lore")] = 5
	elder.State.Location = "square"
	elder.State.Gold = 30
	agents = append(agents, elder)

	// 2. Blacksmith
	blacksmith := NewAgent(
		NewIdentity("agent_blacksmith", "Forge Master Torin", RoleBlacksmith),
		NewDefaultSchedule(),
	)
	blacksmith.Identity.Traits = []string{"diligent", "proud", "honest"}
	blacksmith.Identity.Skills[SkillName("metalwork")] = 5
	blacksmith.Identity.Skills[SkillName("repair")] = 4
	blacksmith.State.Location = "workshop"
	blacksmith.State.Gold = 50
	agents = append(agents, blacksmith)

	// 3. Carpenter
	carpenter := NewAgent(
		NewIdentity("agent_carpenter", "Carpenter Lina", RoleCarpenter),
		NewDefaultSchedule(),
	)
	carpenter.Identity.Traits = []string{"creative", "precise", "quiet"}
	carpenter.Identity.Skills[SkillName("woodwork")] = 5
	carpenter.Identity.Skills[SkillName("building")] = 3
	carpenter.State.Location = "workshop"
	carpenter.State.Gold = 40
	agents = append(agents, carpenter)

	// 4. Forager
	forager := NewAgent(
		NewIdentity("agent_forager", "Forager Fern", RoleForager),
		NewDefaultSchedule(),
	)
	forager.Identity.Traits = []string{"observant", "resourceful", "independent"}
	forager.Identity.Skills[SkillName("foraging")] = 5
	forager.Identity.Skills[SkillName("herbalism")] = 3
	forager.State.Location = "wilderness"
	forager.State.Gold = 15
	agents = append(agents, forager)

	// 5. Scout
	scout := NewAgent(
		NewIdentity("agent_scout", "Scout Rowan", RoleScout),
		NewDefaultSchedule(),
	)
	scout.Identity.Traits = []string{"curious", "brave", "restless"}
	scout.Identity.Skills[SkillName("navigation")] = 5
	scout.Identity.Skills[SkillName("tracking")] = 4
	scout.State.Location = "wilderness"
	scout.State.Gold = 20
	agents = append(agents, scout)

	// 6. Merchant
	merchant := NewAgent(
		NewIdentity("agent_merchant", "Merchant Vesper", RoleMerchant),
		NewDefaultSchedule(),
	)
	merchant.Identity.Traits = []string{"social", "shrewd", "charming"}
	merchant.Identity.Skills[SkillName("negotiation")] = 5
	merchant.Identity.Skills[SkillName("appraisal")] = 4
	merchant.State.Location = "square"
	merchant.State.Gold = 100
	agents = append(agents, merchant)

	// 7. Teacher
	teacher := NewAgent(
		NewIdentity("agent_teacher", "Teacher Alden", RoleTeacher),
		NewDefaultSchedule(),
	)
	teacher.Identity.Traits = []string{"social", "patient", "knowledgeable"}
	teacher.Identity.Skills[SkillName("teaching")] = 5
	teacher.Identity.Skills[SkillName("literacy")] = 4
	teacher.State.Location = "square"
	teacher.State.Gold = 35
	agents = append(agents, teacher)

	// 8. Farmer
	farmer := NewAgent(
		NewIdentity("agent_farmer", "Farmer Clay", RoleFarmer),
		NewDefaultSchedule(),
	)
	farmer.Identity.Traits = []string{"patient", "diligent", "quiet"}
	farmer.Identity.Skills[SkillName("farming")] = 5
	farmer.Identity.Skills[SkillName("animal_handling")] = 3
	farmer.State.Location = "wilderness"
	farmer.State.Gold = 25
	agents = append(agents, farmer)

	// 9. Storyteller
	storyteller := NewAgent(
		NewIdentity("agent_storyteller", "Storyteller Iris", RoleStoryteller),
		NewDefaultSchedule(),
	)
	storyteller.Identity.Traits = []string{"social", "creative", "charismatic"}
	storyteller.Identity.Skills[SkillName("storytelling")] = 5
	storyteller.Identity.Skills[SkillName("performance")] = 4
	storyteller.State.Location = "square"
	storyteller.State.Gold = 20
	agents = append(agents, storyteller)

	// 10. Player slot
	player := NewAgent(
		NewIdentity("agent_player", "Traveler", RolePlayer),
		NewDefaultSchedule(),
	)
	player.Identity.Traits = []string{"adaptable", "curious"}
	player.Identity.Skills[SkillName("adaptability")] = 3
	player.State.Location = "square"
	player.State.Gold = 10
	agents = append(agents, player)

	// Initialize social ties: everyone starts neutral toward everyone
	for i, a := range agents {
		for j, b := range agents {
			if i != j {
				a.State.SocialTies[b.Identity.ID] = 0.0
			}
		}
	}

	// Add initial goals per agent
	elder.AddGoal(&Goal{ID: "g_elder_1", Description: "preserve_knowledge", BasePriority: 8, Urgency: 0.3})
	blacksmith.AddGoal(&Goal{ID: "g_blacksmith_1", Description: "craft_tools", BasePriority: 9, Urgency: 0.5})
	carpenter.AddGoal(&Goal{ID: "g_carpenter_1", Description: "build_furniture", BasePriority: 8, Urgency: 0.4})
	forager.AddGoal(&Goal{ID: "g_forager_1", Description: "gather_food", BasePriority: 10, Urgency: 0.7})
	scout.AddGoal(&Goal{ID: "g_scout_1", Description: "explore_wilderness", BasePriority: 9, Urgency: 0.5})
	merchant.AddGoal(&Goal{ID: "g_merchant_1", Description: "trade_goods", BasePriority: 9, Urgency: 0.6})
	teacher.AddGoal(&Goal{ID: "g_teacher_1", Description: "teach_skills", BasePriority: 8, Urgency: 0.3})
	farmer.AddGoal(&Goal{ID: "g_farmer_1", Description: "grow_crops", BasePriority: 10, Urgency: 0.6})
	storyteller.AddGoal(&Goal{ID: "g_storyteller_1", Description: "collect_stories", BasePriority: 7, Urgency: 0.3})
	player.AddGoal(&Goal{ID: "g_player_1", Description: "explore_town", BasePriority: 6, Urgency: 0.2})

	return agents
}
