

Introduction

To solve challenging motion control problems in robotics (locomotion, manipulation, vehicle control, etc.), many approaches now include a type of mathematical optimization that has no closed-form solution and that is solved numerically, either online (trajectory optimization [1], model predictive control [2], etc.) or offline (reinforcement learning [3]). Numerical tools, however, have a major drawback compared to simpler analytical approaches: the parameters of the problem do not appear explicitly in the solutions, which makes it much harder to generalize and reuse the results. Analytical solutions to control problems have the useful property of allowing the solution to be adjusted to different system parameters by simply substituting the new values in the equation. For instance, an analytical feedback law solution to a robot motion control problem can be transferred to a similar system by adjusting the values of parameters (lengths, masses, etc.) in the equation. However, with a reinforcement learning solution, we would have to re-conduct
A very promising application of the concept of dimensionless policies is to empower reinforcement learning schemes, for which data efficiency is critical [5]. For instance, it would be interesting to use the data of all vehicles on the road, even if they are of varying dimensions and dynamic characteristics, to learn appropriate maneuvers in situations
1Alexandre Girard with the Department Mechanical Engineering, Universite Sherbrooke, Qc, Canada alex.girard@usherbrooke.ca
that occur very rarely. This idea of reusing data or results in a different context is usually called transfer learning [6] and has received a great deal of research attention, mostly targeted at applying a learned policy to new tasks. The more specific idea of transferring policies and data between systems/robots has also been explored, with schemes based on modular blocks [7], invariant features [8], a dynamic map [9], a vector representation of each robot hardware [10], or using tools from adaptive control [11] and robust control [12]. Dimensionless numbers and dimensional analysis comprise a technique based on the idea that some relationships should not depend on units that can be used for analyzing many physical problems [13] [14] [4]. The most well-known application in the field of fluid mechanics is the idea of matching ratios (i.e., Reynolds, Prandtl, or Mach numbers) to allow for the generalization of experimental results between systems of various scales. The recent success of machine learning and data-driven schemes bring front and center the question of generalizing results, and there is a renewed interest in using dimensional analysis in the context of learning [15] [16] [17]. In this paper, we present an initial exploration of how dimensional analysis can be applied specifically to help generalize policy solutions for motion control problems involving physically meaningful variables like force, length, mass, and time.
II. DIMENSIONLESS POLICIES
In the following section, we develop the concept of dimensionless policies based on the Buckingham π theorem and present generic theoretical results that are relevant for any type of physically meaningful control policies.
A. Context variables in the policy mapping
Here, we call a feedback law a mapping f, specific to a given system, from a vector space representing the state x of the dynamic system to a vector space representing the control inputs u of the system:
![Formula - p002_formula01.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p002_formula01.png)

Under some assumptions (fully observable systems, additive cost and infinite time horizon) the optimal feedback law is guarantee to be in this state feedback form [18]. We will only consider motion control problems that lead to this type of time-independent feedback laws in the following analysis. To consider the question of how can this system-specific feedback law be transferred to a different context, it is useful to think about a higher dimension mapping π, which is herein referred to as a policy, also having a vector of variables c describing the context as an additional input argument as illustrated in Figure 2.ii
Definition 1: A policy is defined as the solution to a motion control problem in the form of a function computing the control inputs u from the system states x and context parameters c as follow:
![Formula - p002_formula02.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p002_formula02.png)

![Formula - p002_formula03.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p002_formula03.png)

where k is the dimension of the control input vector, n is the dimension of the dynamic system state vector and k is the dimension of the vector of context parameters.i
The context c is a vector of relevant parameters defining the motion control problem, i.e., parameters that affect the feedback law solution. The policy π is thus a mapping consisting of the feedback law solutions for all possible contexts. In Section III-A, a case study is conducted by considering the optimal feedback law for swinging up a torque-limited inverted pendulum. For this example, the context variables are the pendulum mass m, the gravitational constant g, and the length l, as well as what we call task parameters: a weight parameter in the cost function q and a constraint τmax on the maximum input torque. For a given pendulum state, the optimal torque is also a function of the context variables, i.e., the solution is different if the pendulum is heavier or more torque limited.
![Figure - p002_picture02.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p002_picture02.png)

Fig. 2: The policy π is a feedback law that also includes problem parameters as additional arguments.
Definition 2: A feedback law with a subscript letter a is defined as the solution to a motion problem for a specific situation defined by an instance of context variables ca, as follow:
fa (x) = π (x, c = ca) (4) The feedback law fa thus represents a slice of the global policy when the context variables are fixed at ca values as illustrated in Figure 3.
![Figure - p002_picture03.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p002_picture03.png)

Fig. 3: A feedback law f is a slice of the higher dimensional policy mapping π in a specific context.
The goal of generalizing a feedback law to a different context can thus be formulated into the following question: If a feedback law fa is known for a context described by variables ca, can this knowledge help us deduce the policy solution in a different context, namely cb? π (x, c = ca) = fa (x) π (x, c = cb) = ? (5) Using the Buckingham π theorem [4], we will show that if the context is dimensionally similar, then both feedback laws must be equal up to scaling factors (Theorem 2).


B. Buckingham π theorem

The Buckingham π theorem [4], is a tool based on dimensional analysis [13] [14], that allow to restate a relationship involving multiple physically meaningful dimensional variables, using a lesser number of dimensionless variables:
If d fundamental dimensions are involved in the n dimensional variables (for instance time [T], length [L] and mass [M]), then the number of required dimensionless variables, often called Π groups is p ≥n −d. In most situations, the number of variables in the relationship can be reduced directly by the number of fundamental dimensions involved and p = n −d. The Buckingham π theorem provides a methodology to generate the Π groups, however the choice of Π groups is not unique. The approach is to select (arbitrarily) d variables involving the d fundamental dimensions independently, called the repeated variables. Then, the Π groups are generated by multiplicating all the other variables, by the repeated variables exponentiated by rational exponents selected to make the group dimensionless. Assuming x1, ... xd, where the selected repeated variables, the Π groups are:
![Formula - p003_formula04.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula04.png)

Finding the correct exponents to make all group dimensionless can be formulated as solving a linear system of d equations. We refer to previous literature for more details on the theorem, and here use it specifically on the defined concept of policy map.


C. Dimensional analysis of the policy mapping

If a policy is physically meaningful (for example, a policy that computes a force based on position and velocity, but not a policy for playing chess), we can use the Buckingham π theorem to simplify the policy in dimensionless form.
Theorem 1: If a policy is physically meaningful and all its variables involve d fundamental dimensions that are independently present in the context variables c, then the policy can be restated in a dimensionless form as follow:
![Formula - p003_formula05.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula05.png)

where the dimensionless variables can be related to dimensional variables using transformation matrices that depends only on the context variables as follow:
![Formula - p003_formula06.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula06.png)

![Formula - p003_formula07.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula07.png)

![Formula - p003_formula08.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula08.png)

Furthermore, the transformation matrices can be used to relate the dimensional and dimensionless policy as follow:
![Formula - p003_formula09.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula09.png)

Proof: For a system with k control inputs, we can treat the policy as k mappings from states and context variables to each scalar control input uj:
where Equation (14) is the jth line of the policy in vector form, as described by Equation (2). Then, if the state vector is defined by n variables, and the context is defined by m (system and task) parameters, then each mapping πj is a relation between 1 + n + m variables. Under the assumption that the policy involves physically meaningful variables, and that it is invariant under an arbitrary scaling of any fundamental dimensions– i.e. independent of a system of units–, then we can apply the Buckingham π theorem [4] to conclude that if d dimensions are involved in all of those variables, then Equation (14) can be restated into an equivalent relationship between p dimensionless Π groups where p ≥1 + n + m −d. Assuming that d dimensions are involved in the m context variables, and that we are in the typical scenario where maximum reduction is possible (p = 1 + n + m −d), then we can select d context variables {c1, c2, . . . , cd} as the basis (the repeated variables) to scale all other variables into dimensionless Π groups. We denote dimensionless Π group as the base variables with an asterisk (*), as follows:
![Formula - p003_formula10.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula10.png)

![Formula - p003_formula11.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula11.png)

![Formula - p003_formula12.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula12.png)

where exponents eij are rational numbers selected to make all equations dimensionless. We can then define transformation matrices and write Equations (15), (16), and (17) in a vector form where the repeated variables are grouped into matrices defined as shown at Equations (18), (19) and (20) which correspond to Equations (10), (11) and (12). Matrices Tu and Tx are square diagonal matrices and Equations (10) and (11) are thus inversibles (unless a repeated variable is equal to zero) and can be used to go back and forth between dimensional and dimensionless states and input variables. Matrix Tc consist in a block of d columns of zeros, followed by a diagonal block of dimensions (m −d) × (m −d), and Equation (12) is not inversible. For a given context c, there is only one dimensionless context c∗, however a given dimensionless context c∗may correspond to multiple dimensional contexts c.
Then, the Buckingham π theorem tell us that the relationship described by Equation (14) can be restated in a relationship between the Π groups involving d less variables, which based on the selected repeated variable correspond to:
![Formula - p003_formula13.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p003_formula13.png)

By applying the same procedure to all control inputs, we can then assemble all k mappings back into a vector form,
![Figure - p004_picture04.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_picture04.png)

as follows:
![Figure - p004_picture05.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_picture05.png)

that correspond to Equation (8). Finally, based on the defined transformations at Equations (10), (11) and (12) we can relate the dimensional policy to the dimensionless version as follow:
![Figure - p004_picture06.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_picture06.png)

which correspond to Equation (13).


D. Transferring feedback laws between similar systems

Based on the dimensional analysis, we can demonstrate that any feedback law can be generalized to a different context, under the condition of dimensional similarity. In this section, we show that a feedback law can be transferred exactly to another motion control problem by scaling the input and output of the function based on matrices that can be computed using the dimensional analysis. The salient feature of this result is that the conditions are very generic, even a black-box discontinuous non-linear policy (such as those obtained using deep-reinforcement learning algorithms) can be transferred this way. The limitation is that the condition for an exact transfer is having equal dimensionless context variables c∗.i
First, it is useful to define dimensionless feedback laws that correspond to specific cases of the dimensionless policy, as we defined for the dimensional mapping.i
Definition 3: We denote a dimensionless feedback law f ∗ the global dimensionless policy for a specific instance of
context variables ca, as follow:
where c∗ a is the dimensionless version of the context variables instance ca, and equal to:
![Formula - p004_formula14.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_formula14.png)

Lemma 1: Two feedback laws, that are solutions to the same motion control problem for two instance of context variables, will be equal in dimensionless form if they share the same dimensionless context: b (x∗) = f ∗ a(x∗) ∀x∗ a = c∗ (26) Proof: This follow from the definition:
![Formula - p004_formula15.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_formula15.png)

![Formula - p004_formula16.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_formula16.png)

Lemma 2: In a specific context described by variables ca, a dimensional feedback law can be restated into a dimensionless form, and vice versa, by scaling the input and the output using the defined transformation matrices Tx(ca) and Tu(ca) as follow:
![Figure - p004_picture07.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_picture07.png)

Proof: Starting from Equation 13 and substituting c∗ with a specific instance c∗ a, then substituting policy maps on each side with feedback laws fa and f ∗ a based on the definition, we obtain Equation 30:
![Formula - p004_formula17.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_formula17.png)

![Formula - p004_formula18.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p004_formula18.png)

Then, starting from the right side of Equation 31 and substituting the function fa with Equation 30, the matrices are reduced to identity matrices and we obtain Equation 31:
![Formula - p005_formula19.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_formula19.png)

Theorem 2: If a feedback law fa is known—for instance, as the result of a numerical algorithm—and this is the solution to a motion control problem with context variables ca, we can compute the solution fb to the same motion control problem for different context variables cb by scaling the input and output of fa as follow:
![Formula - p005_formula20.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_formula20.png)

if the contexts ca and cb are dimensionally similar, i.e., if the following condition is true:
![Formula - p005_formula21.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_formula21.png)

Proof: First, fb can be written based on its dimensionless form f ∗ b in a context cb using Equation (30) from Lemma 2. Also, based on Lemma 1, under the similarity condition—i.e. c∗ b = c∗ a or equivalently T(cb)cb = T(ca)ca— we have that f ∗ b is equal to f ∗ a. Finally, f ∗ a can be written based on its dimensional form fa in a context ca, using Equation (31) from Lemma 2, as follow:
![Formula - p005_formula22.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_formula22.png)

![Formula - p005_formula23.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_formula23.png)

![Formula - p005_formula24.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_formula24.png)

The idea is summarized in Figure 4. To transfer a feedback law, we must first extract the dimensionless form, a more generic form of knowledge, and then scale it back to the new context.
![Figure - p005_picture08.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_picture08.png)

Specific non-transferable
Generic conditionally transferable
Fig. 4: Isolating the dimensionless knowledge in a policy allow its exact transfer to any dimensionally similar motion control problem.


E. Dimensionally similar contexts

Equation (35) can be used to scale a policy for an exact transfer of policy solutions between context c sharing the same dimensionless context c∗, a condition that is refer to as dimensionally similar. Equation (12) is a mapping from a m dimensional space to a m −d dimensional space, and
its inverse has multiple solutions. A given dimensionless context c∗corresponds to a subset of all possible values of dimensional context c. As illustrated at Figure 5 and Figure 6 with low-dimensional examples (m = 2 and d = 1), the subsets of context c leading to the same c∗can be linear if c∗is just a ratio of two variables of the same dimension, or a non-linear curve if c∗involves exponents leading to more a complex polynomial relationship. In general when the context c involves many dimensions, it is important to note that the similarity condition means meeting multiple conditions (one for each element of the vector c∗) in a higherdimensional space as illustrated at Figure 7 for the pendulum swing-up example that is studied in the next section. To some degree, this dimensionally similar context condition is a technique to regroup the motion control problems that are the same up to scaling factors. Therefore, it is also logical that their solutions should be equivalent up to scaling factors.
![Figure - p005_picture09.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_picture09.png)

Fig. 5: Example of dimensionally similar contexts subsets that are lines in a plane (m = 2 and d = 1). Context ca is dimensionally similar to cb but not to cc or cd.
![Figure - p005_picture10.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p005_picture10.png)

Fig. 6: Example of dimensionally similar contexts subsets that are non-linear curves in a plane (m = 2 and d = 1). Context ca is dimensionally similar to cb but not to cc or cd.


F. Summary of the theoretical results

The dimensional analysis lead us to the following relevant theoretical results, that are very generic since no assumptions on the form of the policy function are necessary:
Just for illustrating purposes, lets imagine we have a policy for a spherical submarine where the context is defined by a velocity, a viscosity and a radius. In dimensionless form we would find that the context can be described by a single variable, the Reynolds number, and that 1) learning the policy will be easier in dimensionless form because it is a function of a lesser number of variables and 2) that if we know the feedback law solution for a specific context of velocity, viscosity and radius, then we can actually re-use it for multiple versions of the same motion control problem sharing the same Reynolds number.


III. CASE STUDIES WITH NUMERICAL RESULTS

In this section, we use numerically generated optimal policy solutions for two motion control problem as examples illustrating the salient features of the presented theoretical results of section II and the potential for transfer learning.


A. Optimal pendulum swing-up task

The first numerical example is the classical pendulum swing-up task. This example illustrates that an optimal feedback law in the form of a table look-up generated for a pendulum of a given mass and length, can be transferred to a pendulum of a different mass and length if the motion control problem is dimensionally similar. The example is also used to introduce the concept of regime for motion control problem.
1) Motion control problem: The motion control problem is defined here as finding a feedback law for controlling the dynamic system described by the following differential equation:
![Formula - p006_formula25.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p006_formula25.png)

which minimizes the infinite horizon quadratic cost function given by:
![Formula - p006_formula26.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p006_formula26.png)

subject to input constraints given by:
![Formula - p006_formula27.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p006_formula27.png)

Note that, here, 1) the cost function parameter q has a power of two to allow its value to be in units of torque; 2) it was chosen not to penalize high velocity values for simplicity; 3) the weight multiplying the torque is set to one without a loss of generality, as only the relative values of weights impact the optimal solution; and 4) all parameters are time-independent constants. Thus, assuming that there is no hidden variables and that Equations (40), (41), and (42) fully describe the problem, the solution—i.e., the optimal
policy for all contexts—involves the variables listed in Table I, and should be of the form given by:
![Figure - p006_picture11.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p006_picture11.png)



TABLE I: Pendulum swing-up optimal policy variables



Problem parameters

![Table - p006_table01.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p006_table01.png)

It is interesting to note that while there are three system parameters m, g, and l, they only appear independently in two groups in the dynamic equation. We can thus consider only two system parameters. For convenience, we selected mgl, corresponding to the maximum static gravitational torque (i.e., when the pendulum is horizontal) and the natural frequency ω = l , as listed in Table II.


ABLE II: Pendulum reduced system paramet

![Table - p006_table02.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p006_table02.png)

2) Dimensional analysis: Here, we have one control input, two states, two system parameters, and two task parameters, for a total of 1 + (n = 2) + (m = 4) = 7 variables involved. In those variables, only d = 2 independent dimensions ( ML2T −2 and T −1 ) are present. Using c1 = mgl and c2 = ω as the repeated variables leads to the
following dimensionless groups:
![Formula - p007_formula28.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_formula28.png)

![Formula - p007_formula29.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_formula29.png)

![Formula - p007_formula30.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_formula30.png)

All three torque variables (τ, q, and τmax) are scaled by the maximum gravitational torque, and the pendulum velocity variable is scaled by the natural pendulum frequency. The transformation matrices are thus:
![Figure - p007_picture12.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_picture12.png)

By applying the Buckingham π theorem [4], Equation (43) can be restated as a relationship between the five dimensionless Π groups:
![Formula - p007_formula31.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_formula31.png)

According to the results of Section II, for dimensionally similar swing-up contexts (meaning those with equal q∗ and τ ∗ max ratios), the optimal feedback laws should be equivalent in their dimensionless forms. In other words, the optimal policy fa, found in the specific context ca = [ma, la, ga, qa, τmax,a], and the optimal policy fb, in a second context, cb = [mb, lb, gb, qb, τmax,b], are equal when restated in dimensionless form: f ∗ a = f ∗ b if q∗ a = q∗ b and τ ∗ max,a = max,b. Furthermore, fb can be obtained from fa or vice versa using the scaling formula given by Equation (35) if this condition is met. However, if q∗ a ̸= q∗ b or τ ∗ max,a ̸= max,b, then fa cannot provide us with information on fb without additional assumptions. Figure 7 illustrates that for the pendulum swing-up problem the similarity condition can be represented as a line in a three dimension space created by three dimensional context variables. Each conditions of equal values of q∗and τ ∗ max, is a plane in this space, and the intersection of the two plane is the subset of context meeting the two conditions. Also, it is interesting to note that the fourth context variable ω is not an additional axis here because it is not involved in eq. (51).
![Figure - p007_picture13.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_picture13.png)

Fig. 7: The dimensionally similar subset (equal c∗) can be represented as a line in a 3D space for the pendulum swing-up problem. The feedback law solutions to problem with context variables on the same line are equivalent in dimensionless form.
3) Numerical results: Here, we use a numerical algorithm (methodological details are presented in Section III-A.5) to compute numerical solutions to the motion control problem defined by Equations (40), (41), and (42). The algorithm computes feedback laws in the form of look-up tables, based on a discretized grid of the state space. The optimal (up to discretization errors) feedback laws are computed for nine instances of context variables, which are listed in Table III. In those nine contexts, there are three subsets of three dimensionally similar contexts. Also, each subset includes the same three pendulums: a regular pendulum, one that is two times longer, and one that is twice as heavy (as illustrated in Figure 1). Contexts ca, cb, and cc describe a task where the torque is limited to half the maximum gravitational torque. Contexts cd, ce, and cf describe a task where the application of large torques is highly penalized by the cost function. Contexts cg, ch, and ci describe a task where position errors are highly penalized by the cost function.
TABLE III: Pendulum swing-up problem context variables.
![Table - p007_table03.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p007_table03.png)

Figures 8 to 16 illustrate that, for each subset with equal dimensionless context, the dimensional feedback laws generated look numerically very similar. They are similar up to the scaling of their axis, if we neglect slight differences
due to discretization errors. Furthermore, the figures also illustrate that the dimensionless version of the feedback laws (f ∗), computed using Equation (31), are equal within each dimensionally similar subset. These were the expected results predicted by the dimensional analysis presented in Section II.
In terms of how this can be applied in a practical scenario, we see that if we compute the feedback law given in Figure 8(a), we can obtain the feedback law given in Figure 9(a) directly by scaling the original policy with Equation (35), using the appropriate context variables, without having to recompute. In some sense, Equation (35) provides us with the ability to adjust the feedback law spontaneously to conform with new system parameters mgl or ω, as would be the case with an analytical solution, even when working with black box results in the form of a table look-up. But the equivalence of the scaled solution is only guaranteed within a dimensionally similar context subset, which is the main limitation of this approach. The feedback law given in Figure 8(a) cannot be scaled into the feedback law given in Figure 14(a), for instance, since τ ∗ max and q∗are not equals. It is also interesting to note that trajectory solutions from the same starting point—and computed cost-to-go functions (not illustrated)—are also all equivalent, up to scaling factors, within similar subgroups. Hence, optimal trajectories and cost-to-go solutions could also be shared and transferred between similar systems using the same technique that we demonstrate here for feedback laws.
4) Regimes of solutions: In some situations, changing a context variable will not have any effect on the optimal policy. For instance, for a torque-limited optimal pendulum swing-up problem, augmenting τmax or q while keeping the other value fixed will have little effect above a given threshold. For instance, if we look at the solutions for contexts cd, ce, and cf, using a large amount of torque is so highly penalized by the cost function that the saturation limit does not have much impact on the solution (except for edge cases on the boundary). Thus, we would expect that augmenting τmax would not change the solution. Figures 17 and 18 show a slice (to allow for visualization) of the dimensionless optimal policy solution for various contexts. Figure 17 illustrates the results of changing τ ∗ max while keeping q∗fixed. We can see that when τ ∗ max < 0.3, the policy is almost always on the min–max allowable torque values; this behavior is often called bang–bang. At the other extreme, when τ ∗ max > 2.5, the policy solution is continuous and almost never affected by the saturation. Figure 18 illustrates the results of changing q∗while keeping τ ∗ max fixed. We can see that when q∗< 0.1, the optimal policy solution does not reach min–max saturation, while when q∗> 1.0, the policy is almost always on the min–max allowable values.
We can see that, for extreme context values, two types of behavior occur, illustrated as regions in the dimensionless context space in Figure 19. Those regions are best characterized by a ratio of q∗and τ ∗ max, a new dimensionless value that we define as the ratio of the maximum torque saturation
over the weight parameter in the cost functio
![Formula - p008_formula32.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p008_formula32.png)

When the value of R∗≈1, the policy solution is partially continuous and reaches the min–max value in some other region of the state space, this is a behavior we call the transition regime. When the value of R∗≪1, the constraint on torque drives the solution to exhibit bang–bang behavior. In this region (that we approximate here, based on our sensitivity analysis, as R∗≤0.1), the global policy is only a function of τ ∗ max: π∗(θ∗, ˙ θ∗, q∗, τ ∗ max) ≈π∗(θ∗, ˙ θ∗, τ ∗ max) if R∗≪1 (54) i.e., the value of q∗does not affect the solution. On the other hand, when the value of R∗≫1, the policy is unconstrained. In this region (that we approximate here, based on our sensitivity analysis, as R∗≥10), the global policy is only a function of q∗since the constraint is so far away:
The concept of regime is often leveraged in fluid mechanics. It allows us to generalize results between situations where the relevant dimensionless numbers do not match exactly. For instance, when the Mach number is small (Ma < 0.3), we can generally assume there to be in an incompressible regime where various speeds of sound would not change the behavior much. Here, for the purpose of transferring policy solutions between contexts, this means that the condition of having the same exact dimensionless context variables can be relaxed with an inequality that corresponds to a regime. For instance, if we have two contexts in the unconstrained regime, it is sufficient to match only q∗to create equivalent dimensionless policies.
Proposition 1: If it is assumed that Equation (55) holds, the condition of having equivalent dimensionless feedback laws is relaxed to an inequality for one of the context variables, as follows:
![Formula - p008_formula33.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p008_formula33.png)

a = q∗ and a ≫1 and b ≫1 (57)
Proof: First, if R∗ a ≫1 and R∗ b ≫1 then from Equation (55) we can approximate the policy not to be a function of τ ∗ max:
![Formula - p008_formula34.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p008_formula34.png)

Hence, if q∗ a = q∗ b we have:
![Formula - p008_formula35.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p008_formula35.png)

Also, for two contexts in a bang–bang regime, it is sufficient to match only τ ∗ max to have equivalent dimensionless policies.
Proposition 2: If it is assumed that Equation (54) holds, the condition of having equivalent dimensionless feedback
Proof: First, if R∗ a ≪1 and R∗ b ≪1 then from Equation (54) we can approximate the policy not to be a
Fig. 8: Numerical results for context ca
function of q∗:
![Formula - p009_formula36.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p009_formula36.png)

![Formula - p009_formula37.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p009_formula37.png)

Hence, if τ ∗ max,a = τ ∗ max,a we have:
![Formula - p009_formula38.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p009_formula38.png)

![Formula - p009_formula39.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p009_formula39.png)

Fig. 11: Numerical results for context cd
From another point of view, assuming that one of those regimes applies means that we could have removed one variable from the context at the start of the dimensional analysis. All in all, the impact of identifying such regimes is that we can increase the size of the context subset to which the dimensionless version of the policy should be equivalent, leading to a potentially larger pool of systems that can share a learned policy and numerical results.
5) Methodology: We obtained the optimal feedback law presented in this section using a basic dynamic programming
![Figure - p010_picture14.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p010_picture14.png)

algorithm [18] on a discretized version of the continuous system. The approach is almost equivalent to the value iteration algorithm [5]—which is sometimes referred to as model-based reinforcement learning—with the exception that, here, the total number of iteration steps was fixed (corresponding to a very long time horizon approximating an infinite horizon), instead of the iteration being stopped after reaching a convergence criterion. This approach was chosen to enable the collection of consistent results across all contexts that lead to a wide range of order-of-magnitude cost-to-go solutions. The time step was set to 0.025 s, the
![Figure - p011_picture15.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p011_picture15.png)

![Figure - p011_picture16.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p011_picture16.png)

state space was discretized into an even 501 x 501 grid, and the continuous torque input was discretized into 101 discrete control options. Special out-of-bounds and on-target termination states were included to guarantee convergence [18]. Also, using dynamic programming made the setting of additional parameters to define the domain necessary. Although those parameters should not affect the optimal policy far away from the boundaries, dimensionless versions of those parameters were kept fixed in all the experiments,
![Figure - p011_picture17.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p011_picture17.png)

Fig. 14: Numerical results for context cg
as follows:
![Formula - p011_formula40.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p011_formula40.png)

![Formula - p011_formula41.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p011_formula41.png)

![Formula - p011_formula42.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p011_formula42.png)

where θmax is the range of angles for which the optimal policy is solved, set to one full revolution; ˙ θmax is the range of angular velocity for which the optimal policy is solved; and tf is the time horizon, set to 20 periods of the pendulum using the natural frequency. The source code is
![Figure - p012_picture18.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_picture18.png)

Fig. 17: Optimal dimensionless policy for various contexts: τ ∗= π∗(θ∗, ˙ θ∗= 0, q∗= 0.5, τ ∗ max = [0.1, ..., 5.0]).
![Figure - p012_picture19.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_picture19.png)

Fig. 18: Optimal dimensionless policy for various contexts: τ ∗= π∗(θ∗, ˙ θ∗= 0, q∗= [0.05, ..., 2.0], τ ∗ max = 0.5).
available online at the following link: https://github. com/alx87grd/DimensionlessPolicies, and this Google Colab page allows users to reproduce the results: https://colab.research.google.com/drive/ 1kf3apyHlf5t7XzJ3uVM8mgDsneVK_63r?usp= sharing.


B. Optimal motion for a longitudinal car on a slippery surface

The second numerical example is a simplified car positioning task. We use this example to illustrate that an optimal feedback law in the form of a table look-up generated for a car of a given size, can be transferred to a car of a different size if the motion control problem is dimensionally similar. The example includes state constraints and a different type of non-linearity (i.e. is its not similar to the pendulum swingup) to illustrate how generic the developed dimensionless polices concept are.
1) Motion control problem: The motion control problem is defined here as finding a feedback law to control the
![Figure - p012_picture20.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_picture20.png)

Fig. 19: Regime zones for a torque-limited pendulum swingup problem.
![Figure - p012_picture21.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_picture21.png)

ig. 20: Car positioning motion control proble
dynamic system, as described by the following differential equation:
![Formula - p012_formula43.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_formula43.png)

where µ(s) is the ratio of vertical to horizontal forces on the front wheel, that is, a non-linear function of the front wheel slip s. The above equations represent a simple dynamic model of the longitudinal motion of a car, assuming that the controller can impose the wheel slip of the front wheel and that suspensions are infinitely rigid (but that weight transfer is included). Interestingly, it is already standard practice to model the ground–tire interaction with an empirical curve µ(s) relating two dimensionless variables.i
The objective is to minimize the infinite horizon quadratic cost function given by:
![Formula - p012_formula44.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_formula44.png)

subject to the constraints of keeping ground reaction forces positive, as given by:
![Formula - p012_formula45.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_formula45.png)

![Formula - p012_formula46.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p012_formula46.png)

where the weight transfer potentially limits the allowable motions. Note that the cost function parameter q in this problem has a power of minus two to have a value with units of length, and all parameters are time-independent constants. The solution to this problem, i.e., the optimal policy for all contexts, involves the variables listed in Table IV and should
be of the form given by:
![Formula - p013_formula47.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_formula47.png)



TABLE IV: Longitudinal car optimal policy variables

![Table - p013_table04.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_table04.png)

2) Dimensional analysis: Here, we have one control input, two states, and five context parameters, for a total of 1 + (n = 2) + (m = 5) = 8 variables. Of those variables, only d = 2 independent dimensions (length [L] and time [T]) are present. Using c1 = g and c2 = l as the repeated variables leads to the following dimensionless groups:
![Formula - p013_formula48.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_formula48.png)

![Formula - p013_formula49.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_formula49.png)

![Formula - p013_formula50.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_formula50.png)

![Formula - p013_formula51.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_formula51.png)

All three length variables are scaled by the wheel base, and the velocity variable is scaled using a combination of the wheel base and gravity. The transformation matrices are then
as follows:
By applying the Buckingham π theorem [4], Equation (75) can be restated as a relationship between the six dimensionless Π groups, as follows:
![Formula - p013_formula52.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_formula52.png)

3) Numerical results: Here, as in the pendulum example, numerical solutions to the motion control problem are computed for the nine instances of context variables listed in Table V. In those nine contexts, there are three subsets of three dimensionally similar contexts. Contexts ca, cb, and cc describe situations where the CG. horizontal position is at half the wheel base; contexts cd, ce and cf describe situations in which the the CG is very high (and hence the cars are very limited by the weight transfer); and contexts ch, ci, and cj describe situations in which position errors are highly penalized by the cost function plus cars with a very low CG relative to the wheel base.
TABLE V: Car problem parameters.
![Table - p013_table05.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p013_table05.png)

Figures 21 to 29 illustrate that, for each subset with an equal dimensionless context, solutions are equal within each dimensionally similar subset when scaled into the dimensionless form. This was, again, the expected result predicted by the dimensional analysis presented in Section II. In terms of how to use this in a practical scenario, this exemplifies how various cars (which are different but which share the same ratios) could share a braking policy, for instance.
![Figure - p014_picture22.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture22.png)

Fig. 21: Numerical results for context ca.
![Figure - p014_picture23.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture23.png)

![Figure - p014_picture24.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture24.png)

Fig. 22: Numerical results for context cb.
![Figure - p014_picture25.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture25.png)

![Figure - p014_picture26.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture26.png)

Fig. 23: Numerical results for context cc.
![Figure - p014_picture27.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture27.png)

![Figure - p014_picture28.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture28.png)

Fig. 24: Numerical results for context cd.
![Figure - p014_picture29.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p014_picture29.png)

![Figure - p015_picture30.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture30.png)

Fig. 25: Numerical results for context ce.
![Figure - p015_picture31.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture31.png)

![Figure - p015_picture32.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture32.png)

Fig. 26: Numerical results for context cf.
![Figure - p015_picture33.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture33.png)

![Figure - p015_picture34.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture34.png)

Fig. 27: Numerical results for context cg.
![Figure - p015_picture35.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture35.png)

![Figure - p015_picture36.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture36.png)

Fig. 28: Numerical results for context ch.
![Figure - p015_picture37.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture37.png)

![Figure - p015_picture38.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p015_picture38.png)

![Figure - p016_picture39.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_picture39.png)

4) Methodology: The same methodology as the pendulum example (see Section III-A.5) was used for the car motion control problem. The time step was set to 0.025 s, the state space was discretized into an even 501 x 501 grid, and the continuous slip input was discretized into 101 discrete control options. Additional domain parameters were set as follows:
![Formula - p016_formula53.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_formula53.png)

![Formula - p016_formula54.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_formula54.png)

![Formula - p016_formula55.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_formula55.png)

The source code is available online at the following link: https://github.com/alx87grd/ DimensionlessPolicies, and this Google Colab page allows users reproduce the results: https://colab.research.google.com/drive/ 1-CSiLKiNLqq9JC3EFLqjR1fRdICI7e7M?usp= share_link.


IV. CASE STUDIES WITH CLOSED-FORM PARAMETRIC POLICIES

To better understand the concept of a dimensionless policy, in this section two examples based on well-known closedform solutions to classical motion control problems are presented to illustrate how using Theorem 2 can be equivalent to substituting new system parameters in an analytical solution.


A. Dimensionless linear quadratic regulator

The first example is based on the linear quadratic regulator (LQR) solution [19] for the linearized pendulum that allows for a closed-form analytical solution of optimal policy. This allow us to compared the method of transferring the policy with the proposed scaling law of Equation (35), to the method of transferring the policy by substituting the new system parameters in the analytical solution.i
Here, we consider a simplified version of the pendulum swing-up problem (see Section III-A) and a linearized version of the equation of motion is used, as follows:
![Formula - p016_formula56.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_formula56.png)

The same infinite horizon quadratic cost function is used, as follows:
![Formula - p016_formula57.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_formula57.png)

However, no constraints on the torque are included in this problem. All parameters are also assumed to be timeindependent constant. The same variables are used in this problem definition as before, except that the torque limit τmax variable is absent. The global policy solution should then have the following form:
![Figure - p016_picture40.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_picture40.png)

We can thus select the same dimensionless Π groups as in Section III-A.2 and conclude that Equation (91) can be restated under the following dimensionless form:
![Formula - p016_formula58.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_formula58.png)

Proposition 3: For this motion control problem, defined by Equation (89) and Equation (90), an analytical solution exists and the optimal policy is given by:
![Figure - p016_picture41.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p016_picture41.png)

Proof: See Appendix.
Applying Equation (31) to this feedback law leads to the dimensionless form, using G = mgl and H = ml2 for
shortness, as follows:
![Formula - p017_formula59.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula59.png)

![Figure - p017_picture42.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_picture42.png)

The dimensionless policy is only a function of the dimensionless states and the dimensionless cost parameter q∗, as predicted by Equation (92) based on the dimensional analysis. It is interesting to note that Equation (97) represents the core generic solution to the LQR problem and is independent of unit and scale.
We can also use this analytical policy solution to demonstrate Theorem 2, i.e. show that scaling the policy with Equation (35) is equivalent to substituting new context variables when the contexts are dimensionally similar.
Proposition 4: Suppose that we have two context instances, labeled a and b, and that we use the global policy solution of Equation (93) to obtain two versions of contextspecific feedback laws:
![Formula - p017_formula60.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula60.png)

![Formula - p017_formula61.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula61.png)

where
![Formula - p017_formula62.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula62.png)

![Formula - p017_formula63.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula63.png)

Based on Theorem 2, if q∗ a = q∗ b we can obtain fb directly by scaling fa based on Equation (35) as follow:
![Formula - p017_formula64.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula64.png)

where
![Formula - p017_formula65.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula65.png)

Proof: If we substitute fa in Equation (102) by the analytical solution given by Equation (98), and then distribute the multiplying scaling factors we obtain:
![Formula - p017_formula66.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula66.png)

![Formula - p017_formula67.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula67.png)

![Formula - p017_formula68.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula68.png)

which is equivalent to Equation (99) when
![Formula - p017_formula69.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula69.png)

which is the condition of having equal dimensionless contexts (c∗ a = c∗ b) for this motion control problem.
This example illustrates that applying the scaling of Equation (35) based on the dimensional analysis framework is equivalent to changing the context variables in an analytical solution when the dimensionless context variables are equal.


B. Dimensionless computed torque

The second example is again based on the pendulum, but using the computed torque control technique [20]. This also allow us to compared the method of transferring the policy with the proposed scaling law of Equation (35), to the method of transferring the policy by substituting the new system parameters in the analytical solution. This example is not based on a quadratic cost function, as opposed to previous examples, to illustrate the flexibility of the proposed schemes.
Here, we present a second analytical example, A computed torque feedback law is a model-based policy (assuming that there are no torque limits) that is the solution to the motion control problem of making a mechanical system that converges on a desired trajectory, with a specified second-order exponential time profile defined by the following equation:
![Formula - p017_formula70.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p017_formula70.png)

For the specific case of the pendulum-swing up problem, we assume that all parameters are time-independent constants and that our desired trajectory is simply the upright position θd = ˙ θd = θd = 0), leaving only two parameters to define the tasks: ωd and ζ. Then, the computed torque policy takes
the following form:
![Figure - p018_picture43.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_picture43.png)

and the analytical solution is as follows:
τ = mgl sin θ −2ml2ωdζ ˙ θ −ml2ω2 (110)
Here, the context includes the system parameters and two variables characterizing the convergence speed. Note that the task parameters directly define the desired behavior, as opposed to the previous examples where they were defining the behavior indirectly thought a cost function. The states, control inputs, and system parameters are the same as before; only the task parameters differ, and their dimensions are presented in Table VI.


TABLE VI: Computed torque task variables.

![Table - p018_table06.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_table06.png)

Here, seven variables and only p = 2 independent dimensions ( ML2T −2 and T −1 ) are involved. Thus, five dimensionless groups can be formed, as follows:
Using mgl and ω, the system parameters, as the repeating variables leads to the following dimensionless groups:
![Formula - p018_formula71.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula71.png)

![Formula - p018_formula72.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula72.png)

![Formula - p018_formula73.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula73.png)

![Formula - p018_formula74.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula74.png)

Then, applying the Buckingham π theorem tells us that the computed torque policy can be restated as the following relationship between the dimensionless variables:
![Formula - p018_formula75.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula75.png)

Here, we can confirm directly (since we have an analytical solution) that applying Equation (31) to the computed torque
feedback law given by Equation (110) leads to the following dimensionless form:
![Formula - p018_formula76.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula76.png)

![Formula - p018_formula77.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula77.png)

thereby confirming the structure predicted by Equation (117) based on the dimensional analysis.
We can, again, use this example to demonstrate Theorem 2 and show that, when the dimensionless context is equal, scaling a policy using Equation (35) is equivalent to substituting new values of the system parameters into the analytical equation.
Proposition 5: Suppose that we have two context instances, labeled a and b, and that we use the global policy solution of Equation (110) to obtain two versions of contextspecific feedback laws:
![Formula - p018_formula78.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula78.png)

![Formula - p018_formula79.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula79.png)

Based on Theorem 2, if ω∗ d,a = ω∗ d,b and ζ∗ a = ζ∗ b we can obtain fb directly by scaling fa based on Equation (35) as follow:
![Formula - p018_formula80.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula80.png)

Proof: If we substitute fa in Equation (122) by the analytical solution given by Equation (120), and then distribute the multiplying scaling factors we obtain:
![Formula - p018_formula81.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula81.png)

![Formula - p018_formula82.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula82.png)

![Formula - p018_formula83.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula83.png)

which is exactly equivalent to Equation (121) (i.e., equivalent to substituting the a instance of the context variables to the b instance) if:
![Formula - p018_formula84.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula84.png)

which is the dimensional similarity condition (c∗ a = c∗ b) for this motion control problem:
![Formula - p018_formula85.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p018_formula85.png)



V. CONCLUSION

The dimensional analysis of physically meaningful control policies, leveraging the Buckingham π theorem, leads to two interesting theoretical results: 1) In dimensionless form, the solution to a motion control problem involves a reduced number of parameters. 2) It is possible to exactly transfer a feedback law between similar systems without any approximation, simply by scaling the input and output of any type of control law appropriately, including via numerically generated black box mapping. However, the main practical limitation of this approach is that if the condition of dimensional similarity (c∗ a = c∗ b) is not met exactly, then there is no theoretical guarantees regarding whether a policy is transferable without additional assumptions, as the discussed concept of regimes of behaviour. Also, we demonstrated how those results can be used to transfer exactly even discontinuous black-box policies between similar systems, using two simple examples of dynamical systems and numerically generated optimal feedback laws. An interesting direction for further exploration would be investigating how good an approximation is when a feedback law is transferred from a context that is not exactly similar but close. Also, it would be interesting to test the concept of dimensionless policies to empower a reinforcement learning scheme that could collect data from various, but dimensionally similar, systems to accelerate the learning process.


APPENDIX

In this section, we show that the policy given by Equation (93) is optimal with respect to the LQR problem defined in Section IV-A. We can write the equation of motion given by Equation (89) in state-space form, using G = mgl and H = ml2, as follows:
![Formula - p019_formula86.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula86.png)

Then, by adapting a solution from [21], if we parameterize the weight matrix of the cost function as follows:
![Figure - p019_picture44.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_picture44.png)

the optimal cost-to-go is given by:
![Formula - p019_formula87.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula87.png)

and the optimal feedback policy is given by:
![Formula - p019_formula88.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula88.png)

This solution can by verified by substituting matrices into the algebraic Riccati equation given by:
0 = SA + AT S −SBR−1BT S + Q (132)
since the problem fits into the framework of the classical infinite horizon LQR result [18]. Then, we can see that the cost function defined in Section IV-A is a special case, where Q11 = q2 and Q22 = 0, leading to the following equations:
![Formula - p019_formula89.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula89.png)

![Formula - p019_formula90.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula90.png)

Solving for a and b, and retaining the positive solution, leads to the following:
![Formula - p019_formula91.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula91.png)

![Formula - p019_formula92.png](2026-08-13-Girard-2024-DimensionlessPolicies-converted-images/p019_formula92.png)

which, when substituted into Equation (131), is equal to the policy given by Equation (93) in Section IV-A.
