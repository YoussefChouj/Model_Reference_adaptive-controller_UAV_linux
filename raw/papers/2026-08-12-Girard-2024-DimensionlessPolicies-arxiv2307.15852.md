[2307.15852] Dimensionless Policies Based on the Buckingham π Theorem: Is This a Good Way to Generalize Numerical Results?

# Dimensionless Policies Based on the Buckingham $\pi$ Theorem: Is This a Good Way to Generalize Numerical Results?

Alexandre Girard Affiliation: Alexandre Girard is with the Department of Mechanical Engineering, Universite de Sherbrooke, Qc, Canada alex.girard@usherbrooke.ca

###### Abstract

The answer to the question posed in the title is yes if the context (the list of variables defining the motion control problem) is dimensionally similar. This article explores the use of the Buckingham $\pi$ theorem as a tool to encode the control policies of physical systems into a more generic form of knowledge that can be reused in various situations. This approach can be interpreted as enforcing invariance to the scaling of the fundamental units in an algorithm learning a control policy. First, we show, by restating the solution to a motion control problem using dimensionless variables, that (1) the policy mapping involves a reduced number of parameters and (2) control policies generated numerically for a specific system can be transferred exactly to a subset of dimensionally similar systems by scaling the input and output variables appropriately. Those two generic theoretical results are then demonstrated, with numerically generated optimal controllers, for the classic motion control problem of swinging up a torque-limited inverted pendulum and positioning a vehicle in slippery conditions. We also discuss the concept of regime, a region in the space of context variables, that can help to relax the similarity condition. Furthermore, we discuss how applying dimensional scaling of the input and output of a context-specific black-box policy is equivalent to substituting new system parameters in an analytical equation under some conditions, using a linear quadratic regulator (LQR) and a computed torque controller as examples. It remains to be seen how practical this approach can be to generalize policies for more complex high-dimensional problems, but the early results show that it is a promising transfer learning tool for numerical approaches like dynamic programming and reinforcement learning.

## I Introduction

To solve challenging motion control problems in robotics (locomotion, manipulation, vehicle control, etc.), many approaches now include a type of mathematical optimization that has no closed-form solution and that is solved numerically, either online (trajectory optimization [1], model predictive control [2], etc.) or offline (reinforcement learning [3]). Numerical tools, however, have a major drawback compared to simpler analytical approaches: the parameters of the problem do not appear explicitly in the solutions, which makes it much harder to generalize and reuse the results. Analytical solutions to control problems have the useful property of allowing the solution to be adjusted to different system parameters by simply substituting the new values in the equation. For instance, an analytical feedback law solution to a robot motion control problem can be transferred to a similar system by adjusting the values of parameters (lengths, masses, etc.) in the equation. However, with a reinforcement learning solution, we would have to re-conduct all the training, implying (generally) multiple hours of data collection and/or computation. It would be a great asset to have the ability to adjust black box numerical solutions with respect to some problem parameters.

Fig. 1: Shared dimensionless policy for inverted pendulums: Under some conditions various dynamic systems will share the same optimal policy up to scaling factors that can be found based on a dimensional analysis.

In this paper, we explore the concept of dimensionless policies, a more generic form of knowledge conceptually illustrated at Figure 1, as an approach to generalize numerical solutions to motion control problems. First, in Section II, we use dimensional analysis (i.e., the Buckingham $\pi$ theorem [4]) to show that motion control problems with dimensionally similar context variables must share the same feedback law solution when expressed in a dimensionless form, and discuss the implications. Two main generic theoretical results, relevant for any physically meaningful control policies, are presented as Theorem 1 and Theorem 2. Then in Section III we present two case studies with numerical results. Optimal feedback laws computed with a dynamic programming algorithm are used to demonstrate the theoretical results and their relevance for 1) the classical motion control problem of swinging up an inverted pendulum in Section III-A and 2) a car motion control problem in Section III-B. Furthermore, in Section IV, we illustrate—with two examples—how the proposed dimensional scaling is equivalent to changing parameters in an analytical solution.

A very promising application of the concept of dimensionless policies is to empower reinforcement learning schemes, for which data efficiency is critical [5]. For instance, it would be interesting to use the data of all vehicles on the road, even if they are of varying dimensions and dynamic characteristics, to learn appropriate maneuvers in situations that occur very rarely. This idea of reusing data or results in a different context is usually called transfer learning [6] and has received a great deal of research attention, mostly targeted at applying a learned policy to new tasks. The more specific idea of transferring policies and data between systems/robots has also been explored, with schemes based on modular blocks [7], invariant features [8], a dynamic map [9], a vector representation of each robot hardware [10], or using tools from adaptive control [11] and robust control [12]. Dimensionless numbers and dimensional analysis comprise a technique based on the idea that some relationships should not depend on units that can be used for analyzing many physical problems [13] [14] [4]. The most well-known application in the field of fluid mechanics is the idea of matching ratios (i.e., Reynolds, Prandtl, or Mach numbers) to allow for the generalization of experimental results between systems of various scales. The recent success of machine learning and data-driven schemes bring front and center the question of generalizing results, and there is a renewed interest in using dimensional analysis in the context of learning [15] [16] [17]. In this paper, we present an initial exploration of how dimensional analysis can be applied specifically to help generalize policy solutions for motion control problems involving physically meaningful variables like force, length, mass, and time.

## II Dimensionless Policies

In the following section, we develop the concept of dimensionless policies based on the Buckingham $\pi$ theorem and present generic theoretical results that are relevant for any type of physically meaningful control policies.

### II-A Context variables in the policy mapping

Here, we call a feedback law a mapping $f$ , specific to a given system, from a vector space representing the state $x$ of the dynamic system to a vector space representing the control inputs $u$ of the system:

| $$u=f\left(x\right)$$ | (1) |
| --- | --- |

Under some assumptions (fully observable systems, additive cost and infinite time horizon) the optimal feedback law is guarantee to be in this state feedback form [18]. We will only consider motion control problems that lead to this type of time-independent feedback laws in the following analysis. To consider the question of how can this system-specific feedback law be transferred to a different context, it is useful to think about a higher dimension mapping $\pi$ , which is herein referred to as a policy, also having a vector of variables $c$ describing the context as an additional input argument as illustrated in Figure 2.

###### Definition 1

A policy is defined as the solution to a motion control problem in the form of a function computing the control inputs $u$ from the system states $x$ and context parameters $c$ as follow:

| $\displaystyle u=$ | $\displaystyle\pi\left(x,c\right)$ | (2) |
| --- | --- | --- |
| $\displaystyle\textit{with}\quad u\in\mathbf{R}^{k}\quad$ | $\displaystyle x\in\mathbf{R}^{n}\quad c\in\mathbf{R}^{m}$ | (3) |

where $k$ is the dimension of the control input vector, $n$ is the dimension of the dynamic system state vector and $k$ is the dimension of the vector of context parameters.

The context $c$ is a vector of relevant parameters defining the motion control problem, i.e., parameters that affect the feedback law solution. The policy $\pi$ is thus a mapping consisting of the feedback law solutions for all possible contexts. In Section III-A, a case study is conducted by considering the optimal feedback law for swinging up a torque-limited inverted pendulum. For this example, the context variables are the pendulum mass $m$ , the gravitational constant $g$ , and the length $l$ , as well as what we call task parameters: a weight parameter in the cost function $q$ and a constraint $\tau_{max}$ on the maximum input torque. For a given pendulum state, the optimal torque is also a function of the context variables, i.e., the solution is different if the pendulum is heavier or more torque limited.

Fig. 2: The policy $\pi$ is a feedback law that also includes problem parameters as additional arguments.

(a) Generic policy

(b) Inverted pendulum example.

###### Definition 2

A feedback law with a subscript letter $a$ is defined as the solution to a motion problem for a specific situation defined by an instance of context variables $c_{a}$ , as follow:

| $$f_{a}\left(x\right)=\pi\left(x,c=c_{a}\right)\quad\quad\forall x$$ | (4) |
| --- | --- |

The feedback law $f_{a}$ thus represents a slice of the global policy when the context variables are fixed at $c_{a}$ values as illustrated in Figure 3.

Fig. 3: A feedback law $f$ is a slice of the higher dimensional policy mapping $\pi$ in a specific context.

The goal of generalizing a feedback law to a different context can thus be formulated into the following question: If a feedback law $f_{a}$ is known for a context described by variables $c_{a}$ , can this knowledge help us deduce the policy solution in a different context, namely $c_{b}$ ?

| $$\pi\left(x,c=c_{a}\right)=f_{a}\left(x\right)\quad\Rightarrow\quad\pi\left(x,c=c_{b}\right)=\,?\quad$$ | (5) |
| --- | --- |

Using the Buckingham $\pi$ theorem [4], we will show that if the context is dimensionally similar, then both feedback laws must be equal up to scaling factors (Theorem 2).

### II-B Buckingham $\pi$ theorem

The Buckingham $\pi$ theorem [4], is a tool based on dimensional analysis [13] [14], that allow to restate a relationship involving multiple physically meaningful dimensional variables, using a lesser number of dimensionless variables:

| $$x_{1}=f(x_{2},\;\ldots\;,x_{n})\quad\Rightarrow\quad\Pi_{1}=f(\Pi_{2},\ldots,\Pi_{p})$$ | (6) |
| --- | --- |

If $d$ fundamental dimensions are involved in the $n$ dimensional variables (for instance time [T], length [L] and mass [M]), then the number of required dimensionless variables, often called $\Pi$ groups is $p\geq n-d$ . In most situations, the number of variables in the relationship can be reduced directly by the number of fundamental dimensions involved and $p=n-d$ . The Buckingham $\pi$ theorem provides a methodology to generate the $\Pi$ groups, however the choice of $\Pi$ groups is not unique. The approach is to select (arbitrarily) $d$ variables involving the $d$ fundamental dimensions independently, called the repeated variables. Then, the $\Pi$ groups are generated by multiplicating all the other variables, by the repeated variables exponentiated by rational exponents selected to make the group dimensionless. Assuming $x_{1}$ , … $x_{d}$ , where the selected repeated variables, the $\Pi$ groups are:

| $$\Pi_{i}=x_{d+i}\;\underbrace{x_{1}^{e_{1i}}\;x_{2}^{e_{2i}}\ldots x_{d}^{e_{di}}}_{\text{Repeated variables}}\quad i=\{1,...,p\}$$ | (7) |
| --- | --- |

Finding the correct exponents to make all group dimensionless can be formulated as solving a linear system of $d$ equations. We refer to previous literature for more details on the theorem, and here use it specifically on the defined concept of policy map.

### II-C Dimensional analysis of the policy mapping

If a policy is physically meaningful (for example, a policy that computes a force based on position and velocity, but not a policy for playing chess), we can use the Buckingham $\pi$ theorem to simplify the policy in dimensionless form.

###### Theorem 1

If a policy is physically meaningful and all its variables involve $d$ fundamental dimensions that are independently present in the context variables $c$ , then the policy can be restated in a dimensionless form as follow:

| $\displaystyle u=\pi(x,c)\quad\quad$ | $\displaystyle\Rightarrow\quad u^{*}=\pi^{*}(x^{*},c^{*})$ | (8) |
| --- | --- | --- |
| $\displaystyle u\in\mathbf{R}^{k}\;x\in\mathbf{R}^{n}\;c\in\mathbf{R}^{m}\;\;$ | $\displaystyle\;\;u^{*}\in\mathbf{R}^{k}\;x^{*}\in\mathbf{R}^{n}\;c^{*}\in\mathbf{R}^{(m-d)}$ | (9) |

where the dimensionless variables can be related to dimensional variables using transformation matrices that depends only on the context variables as follow:

| $\displaystyle u^{*}$ | $\displaystyle=\left[T_{u}(c)\right]\,u$ | (10) |
| --- | --- | --- |
| $\displaystyle x^{*}$ | $\displaystyle=\left[T_{x}(c)\right]\,x$ | (11) |
| $\displaystyle c^{*}$ | $\displaystyle=\left[T_{c}(c)\right]\,c$ | (12) |

Furthermore, the transformation matrices can be used to relate the dimensional and dimensionless policy as follow:

| $\displaystyle\pi(x,c)=T_{u}^{-1}(c)\;\pi^{*}\Big(\;T_{x}(c)x\;,\;T_{c}(c)c\;\Big)$ | (13) |
| --- | --- |

###### Proof:

For a system with $k$ control inputs, we can treat the policy as $k$ mappings from states and context variables to each scalar control input $u_{j}$ :

| $$u_{j}=\pi_{j}\left(x_{1},\ldots,x_{n},c_{1},\ldots\ldots,c_{m}\right)$$ | (14) |
| --- | --- |

where Equation (14) is the $j$ th line of the policy in vector form, as described by Equation (2). Then, if the state vector is defined by $n$ variables, and the context is defined by $m$ (system and task) parameters, then each mapping $\pi_{j}$ is a relation between $1+n+m$ variables. Under the assumption that the policy involves physically meaningful variables, and that it is invariant under an arbitrary scaling of any fundamental dimensions– i.e. independent of a system of units–, then we can apply the Buckingham $\pi$ theorem [4] to conclude that if $d$ dimensions are involved in all of those variables, then Equation (14) can be restated into an equivalent relationship between $p$ dimensionless $\Pi$ groups where $p\geq 1+n+m-d$ . Assuming that $d$ dimensions are involved in the $m$ context variables, and that we are in the typical scenario where maximum reduction is possible ( $p=1+n+m-d$ ), then we can select $d$ context variables $\{c_{1},c_{2},\ldots,c_{d}\}$ as the basis (the repeated variables) to scale all other variables into dimensionless $\Pi$ groups. We denote dimensionless $\Pi$ group as the base variables with an asterisk (*), as follows:

| $\displaystyle u_{j}^{*}$ | $\displaystyle=u_{j}\left[c_{1}\right]^{e^{u}_{1j}}\left[c_{2}\right]^{e^{u}_{2j}}\ldots\left[c_{d}\right]^{e^{u}_{dj}}\quad\scriptstyle j=\{1,\ldots,k\}$ | (15) |
| --- | --- | --- |
| $\displaystyle x_{i}^{*}$ | $\displaystyle=x_{i}\left[c_{1}\right]^{e^{x}_{1i}}\left[c_{2}\right]^{e^{x}_{2i}}\ldots\left[c_{d}\right]^{e^{x}_{di}}\quad\scriptstyle i=\{1,\ldots,n\}$ | (16) |
| $\displaystyle c_{i}^{*}$ | $\displaystyle=c_{i}\left[c_{1}\right]^{e^{c}_{1i}}\left[c_{2}\right]^{e^{c}_{2i}}\ldots\left[c_{d}\right]^{e^{c}_{di}}\quad\scriptstyle i=\{d+1,\ldots,m\}$ | (17) |

where exponents $e_{ij}$ are rational numbers selected to make all equations dimensionless. We can then define transformation matrices and write Equations (15), (16), and (17) in a vector form where the repeated variables are grouped into matrices defined as shown at Equations (18), (19) and (20)

| $\displaystyle\underbrace{\scriptsize\begin{bmatrix}u_{1}^{*}\\ \vdots\\ u_{k}^{*}\end{bmatrix}}_{u^{*}}$ | $\displaystyle=\underbrace{\scriptsize\begin{bmatrix}\left(\left[c_{1}\right]^{e^{u}_{11}}\left[c_{2}\right]^{e^{u}_{21}}\ldots\left[c_{d}\right]^{e^{u}_{d1}}\right)&0&0\\ 0&\ddots&0\\ 0&0&\left(\left[c_{1}\right]^{e^{u}_{1k}}\left[c_{2}\right]^{e^{u}_{2k}}\ldots\left[c_{d}\right]^{e^{u}_{dk}}\right)\end{bmatrix}}_{T_{u}(c)}\underbrace{\scriptsize\begin{bmatrix}u_{1}\\ \vdots\\ u_{k}\end{bmatrix}}_{u}$ | (18) |
| --- | --- | --- |
| $\displaystyle\underbrace{\scriptsize\begin{bmatrix}x_{1}^{*}\\ \vdots\\ x_{n}^{*}\end{bmatrix}}_{x^{*}}$ | $\displaystyle=\underbrace{\scriptsize\begin{bmatrix}\left(\left[c_{1}\right]^{e^{x}_{11}}\left[c_{2}\right]^{e^{x}_{21}}\ldots\left[c_{d}\right]^{e^{x}_{d1}}\right)&0&0\\ 0&\ddots&0\\ 0&0&\left(\left[c_{1}\right]^{e^{x}_{1n}}\left[c_{2}\right]^{e^{x}_{2n}}\ldots\left[c_{d}\right]^{e^{x}_{dn}}\right)\end{bmatrix}}_{T_{x}(c)}\underbrace{\scriptsize\begin{bmatrix}x_{1}\\ \vdots\\ x_{n}\end{bmatrix}}_{x}$ | (19) |
| $\displaystyle\underbrace{\scriptsize\begin{bmatrix}c_{d+1}^{*}\\ \vdots\\ c_{m}^{*}\end{bmatrix}}_{c^{*}}$ | $\displaystyle=\underbrace{\scriptsize\begin{bmatrix}0&\ldots&0&\left(\left[c_{1}\right]^{e^{u}_{1(d+1)}}\left[c_{2}\right]^{e^{u}_{2(d+1)}}\ldots\left[c_{d}\right]^{e^{u}_{d(d+1)}}\right)&0&0\\ 0&\ldots&0&0&\ddots&0\\ 0&\ldots&0&0&0&\left(\left[c_{1}\right]^{e^{u}_{1m}}\left[c_{2}\right]^{e^{u}_{2m}}\ldots\left[c_{d}\right]^{e^{u}_{dm}}\right)\end{bmatrix}}_{T_{c}(c)}\underbrace{\scriptsize\begin{bmatrix}c_{1}\\ \vdots\\ c_{m}\end{bmatrix}}_{c}$ | (20) |

which correspond to Equations (10), (11) and (12). Matrices $T_{u}$ and $T_{x}$ are square diagonal matrices and Equations (10) and (11) are thus inversibles (unless a repeated variable is equal to zero) and can be used to go back and forth between dimensional and dimensionless states and input variables. Matrix $T_{c}$ consist in a block of $d$ columns of zeros, followed by a diagonal block of dimensions $(m-d)\times(m-d)$ , and Equation (12) is not inversible. For a given context $c$ , there is only one dimensionless context $c^{*}$ , however a given dimensionless context $c^{*}$ may correspond to multiple dimensional contexts $c$ .

Then, the Buckingham $\pi$ theorem tell us that the relationship described by Equation (14) can be restated in a relationship between the $\Pi$ groups involving $d$ less variables, which based on the selected repeated variable correspond to:

| $$u_{j}^{*}=\pi_{j}^{*}\left(x_{1}^{*},\ldots,x_{n}^{*},c_{d+1}^{*},\ldots,c_{m}^{*}\right)$$ | (21) |
| --- | --- |

By applying the same procedure to all control inputs, we can then assemble all $k$ mappings back into a vector form, as follows:

| $$\underbrace{\begin{bmatrix}u_{1}^{*}\\ \vdots\\ u_{k}^{*}\end{bmatrix}=\pi^{*}\Biggl(\begin{bmatrix}x_{1}^{*}\\ \vdots\\ x_{n}^{*}\end{bmatrix}}_{\text{Dimensionless feedback law $f^{*}$}},\underbrace{\begin{bmatrix}c_{d+1}^{*}\\ \vdots\\ c_{m}^{*}\end{bmatrix}}_{\text{context $c^{*}$}}\Biggr)$$ | (22) |
| --- | --- |

that correspond to Equation (8). Finally, based on the defined transformations at Equations (10), (11) and (12) we can relate the dimensional policy to the dimensionless version as follow:

| $\displaystyle\pi(x,c)=\underbrace{T_{u}^{-1}(c)\;\underbrace{\pi^{*}\Big(\;\underbrace{T_{x}(c)x}_{x^{*}}\;,\;\underbrace{T_{c}(c)c}_{c^{*}}\;\Big)}_{u^{*}}}_{u}$ | (23) |
| --- | --- |

which correspond to Equation (13). ∎

### II-D Transferring feedback laws between similar systems

Based on the dimensional analysis, we can demonstrate that any feedback law can be generalized to a different context, under the condition of dimensional similarity. In this section, we show that a feedback law can be transferred exactly to another motion control problem by scaling the input and output of the function based on matrices that can be computed using the dimensional analysis. The salient feature of this result is that the conditions are very generic, even a black-box discontinuous non-linear policy (such as those obtained using deep-reinforcement learning algorithms) can be transferred this way. The limitation is that the condition for an exact transfer is having equal dimensionless context variables $c^{*}$ .

First, it is useful to define dimensionless feedback laws that correspond to specific cases of the dimensionless policy, as we defined for the dimensional mapping.

###### Definition 3

We denote a dimensionless feedback law $f_{a}^{*}$ , the global dimensionless policy for a specific instance of context variables $c_{a}$ , as follow:

| $$f_{a}^{*}(x^{*})=\pi^{*}(x^{*},c^{*}=c^{*}_{a})\quad\forall x^{*}$$ | (24) |
| --- | --- |

where $c^{*}_{a}$ is the dimensionless version of the context variables instance $c_{a}$ , and equal to:

| $$c^{*}_{a}=T_{c}(c_{a})\,c_{a}$$ | (25) |
| --- | --- |

###### Lemma 1

Two feedback laws, that are solutions to the same motion control problem for two instance of context variables, will be equal in dimensionless form if they share the same dimensionless context:

| $$f_{b}^{*}(x^{*})=f_{a}^{*}(x^{*})\quad\forall x^{*}\quad\text{if}\quad c_{a}^{*}=c_{b}^{*}$$ | (26) |
| --- | --- |

###### Proof:

This follow from the definition:

| $\displaystyle f_{a}^{*}(x^{*})$ | $\displaystyle=\pi^{*}(x^{*},c^{*}=c_{a}^{*})$ | (27) |
| --- | --- | --- |
| $\displaystyle f_{a}^{*}(x^{*})$ | $\displaystyle=\pi^{*}(x^{*},c^{*}=c_{b}^{*})$ | (28) |
| $\displaystyle f_{a}^{*}(x^{*})$ | $\displaystyle=f_{b}^{*}(x^{*})$ | (29) |

∎

###### Lemma 2

In a specific context described by variables $c_{a}$ , a dimensional feedback law can be restated into a dimensionless form, and vice versa, by scaling the input and the output using the defined transformation matrices $T_{x}(c_{a})$ and $T_{u}(c_{a})$ as follow:

| $\displaystyle f_{a}(x)$ | $\displaystyle=T^{-1}_{u}(c_{a})\underbrace{f_{a}^{*}\Big(\underbrace{T_{x}(c_{a})\;x}_{x^{*}}\Big)}_{u^{*}}\quad\forall x$ | (30) |
| --- | --- | --- |
| $\displaystyle f_{a}^{*}(x^{*})$ | $\displaystyle=T_{u}(c_{a})\underbrace{f_{a}\Big(\underbrace{T_{x}^{-1}(c_{a})\;x^{*}}_{x}\Big)}_{u}\quad\forall x^{*}$ | (31) |

###### Proof:

Starting from Equation 13 and substituting $c^{*}$ with a specific instance $c^{*}_{a}$ , then substituting policy maps on each side with feedback laws $f_{a}$ and $f_{a}^{*}$ based on the definition, we obtain Equation 30:

| $\displaystyle\pi(x,c_{a})$ | $\displaystyle=T_{u}^{-1}(c_{a})\;\pi^{*}\Big(\;T_{x}(c_{a})x\;,\;T_{c}(c_{a})c_{a}\;\Big)$ | (32) |
| --- | --- | --- |
| $\displaystyle f_{a}(x)$ | $\displaystyle=T_{u}^{-1}(c_{a})f_{a}^{*}\Big(T_{x}(c_{a})\,x\Big)$ | (33) |

Then, starting from the right side of Equation 31 and substituting the function $f_{a}$ with Equation 30, the matrices are reduced to identity matrices and we obtain Equation 31:

| $\displaystyle T_{u}(c_{a})T_{u}^{-1}(c_{a})f_{a}^{*}\Big(T_{x}^{-1}(c_{a})T_{x}(c_{a})\;x^{*}\Big)$ | $\displaystyle=f_{a}^{*}(x^{*})$ | (34) |
| --- | --- | --- |

∎

###### Theorem 2

If a feedback law $f_{a}$ is known—for instance, as the result of a numerical algorithm—and this is the solution to a motion control problem with context variables $c_{a}$ , we can compute the solution $f_{b}$ to the same motion control problem for different context variables $c_{b}$ by scaling the input and output of $f_{a}$ as follow:

| $\displaystyle f_{b}(x)$ | $\displaystyle=\left[T^{-1}_{u}(c_{b})T_{u}(c_{a})\right]\,f_{a}\left(\left[T_{x}^{-1}(c_{a})T_{x}(c_{b})\right]\,x\right)\quad\forall x$ | (35) |
| --- | --- | --- |

if the contexts $c_{a}$ and $c_{b}$ are dimensionally similar, i.e., if the following condition is true:

| $$T_{c}(c_{b})\;c_{b}=T_{c}(c_{a})\;c_{a}$$ | (36) |
| --- | --- |

###### Proof:

First, $f_{b}$ can be written based on its dimensionless form $f_{b}^{*}$ in a context $c_{b}$ using Equation (30) from Lemma 2. Also, based on Lemma 1, under the similarity condition—i.e. $c_{b}^{*}=c_{a}^{*}$ or equivalently $T(c_{b})c_{b}=T(c_{a})c_{a}$ — we have that $f^{*}_{b}$ is equal to $f^{*}_{a}$ . Finally, $f^{*}_{a}$ can be written based on its dimensional form $f_{a}$ in a context $c_{a}$ , using Equation (31) from Lemma 2, as follow:

| $\displaystyle f_{b}(x)$ | $\displaystyle=T^{-1}_{u}(c_{b})f_{b}^{*}\Big(T_{x}(c_{b})\;x\Big)$ | (37) |
| --- | --- | --- |
| $\displaystyle f_{b}(x)$ | $\displaystyle=T^{-1}_{u}(c_{b})f_{a}^{*}\Big(T_{x}(c_{b})\;x\Big)\quad\quad\text{if}\quad c_{b}^{*}=c_{a}^{*}$ | (38) |
| $\displaystyle f_{b}(x)$ | $\displaystyle=\left[T^{-1}_{u}(c_{b})T_{u}(c_{a})\right]\,f_{a}\left(\left[T_{x}^{-1}(c_{a})T_{x}(c_{b})\right]\,x\right)$ | (39) |

∎

The idea is summarized in Figure 4. To transfer a feedback law, we must first extract the dimensionless form, a more generic form of knowledge, and then scale it back to the new context.

Fig. 4: Isolating the dimensionless knowledge in a policy allow its exact transfer to any dimensionally similar motion control problem.

### II-E Dimensionally similar contexts

Equation (35) can be used to scale a policy for an exact transfer of policy solutions between context $c$ sharing the same dimensionless context $c^{*}$ , a condition that is refer to as dimensionally similar. Equation (12) is a mapping from a $m$ dimensional space to a $m-d$ dimensional space, and its inverse has multiple solutions. A given dimensionless context $c^{*}$ corresponds to a subset of all possible values of dimensional context $c$ . As illustrated at Figure 5 and Figure 6 with low-dimensional examples ( $m=2$ and $d=1$ ), the subsets of context $c$ leading to the same $c^{*}$ can be linear if $c^{*}$ is just a ratio of two variables of the same dimension, or a non-linear curve if $c^{*}$ involves exponents leading to more a complex polynomial relationship. In general when the context $c$ involves many dimensions, it is important to note that the similarity condition means meeting multiple conditions (one for each element of the vector $c^{*}$ ) in a higher-dimensional space as illustrated at Figure 7 for the pendulum swing-up example that is studied in the next section. To some degree, this dimensionally similar context condition is a technique to regroup the motion control problems that are the same up to scaling factors. Therefore, it is also logical that their solutions should be equivalent up to scaling factors.

Fig. 5: Example of dimensionally similar contexts subsets that are lines in a plane ( $m=2$ and $d=1$ ). Context $c_{a}$ is dimensionally similar to $c_{b}$ but not to $c_{c}$ or $c_{d}$ .

Fig. 6: Example of dimensionally similar contexts subsets that are non-linear curves in a plane ( $m=2$ and $d=1$ ). Context $c_{a}$ is dimensionally similar to $c_{b}$ but not to $c_{c}$ or $c_{d}$ .

### II-F Summary of the theoretical results

The dimensional analysis lead us to the following relevant theoretical results, that are very generic since no assumptions on the form of the policy function are necessary:

1.

The global problem of learning $\pi(x,c)$ , i.e., the feedback policies for all possible contexts, is simplified in a dimensionless form $\pi^{*}(x^{*},c^{*})$ because we can remove $d$ input dimensions from the unknown mapping (typically, $d$ would be 2 or 3 for controlling a physical system involving time, force, and length), see Theorem 1.

2.

The feedback law solutions of dimensionally similar subset of contexts share the exact same solution when restated in a dimensionless form, see Lemma 1.

3.

A feedback law, which is a solution to a motion control problem in a context can be transferred exactly to another context, under a condition of dimensional similarity, by scaling appropriately its inputs and outputs, see Theorem 2.

Just for illustrating purposes, lets imagine we have a policy for a spherical submarine where the context is defined by a velocity, a viscosity and a radius. In dimensionless form we would find that the context can be described by a single variable, the Reynolds number, and that 1) learning the policy will be easier in dimensionless form because it is a function of a lesser number of variables and 2) that if we know the feedback law solution for a specific context of velocity, viscosity and radius, then we can actually re-use it for multiple versions of the same motion control problem sharing the same Reynolds number.

## III Case studies with numerical results

In this section, we use numerically generated optimal policy solutions for two motion control problem as examples illustrating the salient features of the presented theoretical results of section II and the potential for transfer learning.

### III-A Optimal pendulum swing-up task

The first numerical example is the classical pendulum swing-up task. This example illustrates that an optimal feedback law in the form of a table look-up generated for a pendulum of a given mass and length, can be transferred to a pendulum of a different mass and length if the motion control problem is dimensionally similar. The example is also used to introduce the concept of regime for motion control problem.

#### III-A1 Motion control problem

The motion control problem is defined here as finding a feedback law for controlling the dynamic system described by the following differential equation:

| $$ml^{2}\ddot{\theta}-mgl\sin\theta=\tau$$ | (40) |
| --- | --- |

which minimizes the infinite horizon quadratic cost function given by:

| $$J=\int_{0}^{\infty}{\left(q^{2}\theta^{2}\,+\,\tau^{2}\right)dt}$$ | (41) |
| --- | --- |

subject to input constraints given by:

| $$-\tau_{max}\leq\tau\leq\tau_{max}$$ | (42) |
| --- | --- |

Note that, here, 1) the cost function parameter $q$ has a power of two to allow its value to be in units of torque; 2) it was chosen not to penalize high velocity values for simplicity; 3) the weight multiplying the torque is set to one without a loss of generality, as only the relative values of weights impact the optimal solution; and 4) all parameters are time-independent constants. Thus, assuming that there is no hidden variables and that Equations (40), (41), and (42) fully describe the problem, the solution—i.e., the optimal policy for all contexts—involves the variables listed in Table I, and should be of the form given by:

| $$\underbrace{\tau}_{\text{inputs}}=\pi\left(\underbrace{\theta,\dot{\theta}}_{\text{states}},\underbrace{\underbrace{m,g,l}_{\text{system parameters}},\underbrace{q,\tau_{max}}_{\text{task parameters}}}_{\text{Context $c$}}\right)$$ | (43) |
| --- | --- |

TABLE I: Pendulum swing-up optimal policy variables

. Variable Description Units Dimensions Control inputs $\tau$ Actuator torque $Nm$ [ $ML^{2}T^{-2}$ ] State variables $\theta$ Joint angle $rad$ [] $\dot{\theta}$ Joint angular velocity $rad/sec$ [ $T^{-1}$ ] System parameters $m$ Pendulum mass $kg$ [ $M$ ] $g$ Gravity $m/s^{2}$ [ $LT^{-2}$ ] $l$ Pendulum lenght $m$ [ $L$ ] Problem parameters $q$ Weight parameter $Nm$ [ $ML^{2}T^{-2}$ ] $\tau_{max}$ Maximum torque $Nm$ [ $ML^{2}T^{-2}$ ]

It is interesting to note that while there are three system parameters $m$ , $g$ , and $l$ , they only appear independently in two groups in the dynamic equation. We can thus consider only two system parameters. For convenience, we selected $mgl$ , corresponding to the maximum static gravitational torque (i.e., when the pendulum is horizontal) and the natural frequency $\omega=\sqrt{\frac{g}{l}}$ , as listed in Table II.

TABLE II: Pendulum reduced system parameters

. Variable Description Units Dimensions $mgl$ Maximum gravitational torque $Nm$ [ $ML^{2}T^{-2}$ ] $\omega=\sqrt{\frac{g}{l}}$ Natural frequency $sec^{-1}$ [ $T^{-1}$ ]

#### III-A2 Dimensional analysis

Here, we have one control input, two states, two system parameters, and two task parameters, for a total of $1+(n=2)+(m=4)=7$ variables involved. In those variables, only $d=2$ independent dimensions ( $ML^{2}T^{-2}$ and $T^{-1}$ ) are present. Using $c_{1}=mgl$ and $c_{2}=\omega$ as the repeated variables leads to the following dimensionless groups:

| $\displaystyle\Pi_{1}$ | $\displaystyle=\tau^{*}=\frac{\tau}{mgl}\quad\quad\frac{[ML^{2}T^{-2}]}{[M][LT^{-2}][L]}$ | (44) |
| --- | --- | --- |
| $\displaystyle\Pi_{2}$ | $\displaystyle=\theta^{*}=\theta\quad\quad[]$ | (45) |
| $\displaystyle\Pi_{3}$ | $\displaystyle=\dot{\theta}^{*}=\frac{\dot{\theta}}{\omega}\quad\quad\frac{[T^{-1}]}{[T^{-1}]}$ | (46) |
| $\displaystyle\Pi_{4}$ | $\displaystyle=\tau_{max}^{*}=\frac{\tau_{max}}{mgl}\quad\quad\frac{[ML^{2}T^{-2}]}{[M][LT^{-2}][L]}$ | (47) |
| $\displaystyle\Pi_{5}$ | $\displaystyle=q^{*}=\frac{q}{mgl}\quad\quad\frac{[ML^{2}T^{-2}]}{[M][LT^{-2}][L]}$ | (48) |

All three torque variables ( $\tau$ , $q$ , and $\tau_{max}$ ) are scaled by the maximum gravitational torque, and the pendulum velocity variable is scaled by the natural pendulum frequency. The transformation matrices are thus:

| $\displaystyle\tau^{*}$ | $\displaystyle=\underbrace{\left[1/mgl\right]}_{T_{u}}\,\tau$ | (49) |
| --- | --- | --- |
| $\displaystyle\begin{bmatrix}\theta^{*}\\ \dot{\theta}^{*}\end{bmatrix}$ | $\displaystyle=\underbrace{\begin{bmatrix}1&0\\ 0&1/\omega\end{bmatrix}}_{T_{x}}\,\begin{bmatrix}\theta\\ \dot{\theta}\end{bmatrix}$ | (50) |
| $\displaystyle\underbrace{\begin{bmatrix}q^{*}\\ \tau_{max}^{*}\end{bmatrix}}_{c^{*}}$ | $\displaystyle=\underbrace{\begin{bmatrix}0&0&1/mgl&0\\ 0&0&0&1/mgl\end{bmatrix}}_{T_{c}}\,\underbrace{\begin{bmatrix}mgl\\ \omega\\ q\\ \tau_{max}\end{bmatrix}}_{c}$ | (51) |

By applying the Buckingham $\pi$ theorem [4], Equation (43) can be restated as a relationship between the five dimensionless $\Pi$ groups:

| $$\tau^{*}=\pi^{*}\left(\theta,\dot{\theta}^{*},q^{*},\tau_{max}^{*}\right)$$ | (52) |
| --- | --- |

According to the results of Section II, for dimensionally similar swing-up contexts (meaning those with equal $q^{*}$ and $\tau_{max}^{*}$ ratios), the optimal feedback laws should be equivalent in their dimensionless forms. In other words, the optimal policy $f_{a}$ , found in the specific context $c_{a}=[m_{a},l_{a},g_{a},q_{a},\tau_{max,a}]$ , and the optimal policy $f_{b}$ , in a second context, $c_{b}=[m_{b},l_{b},g_{b},q_{b},\tau_{max,b}]$ , are equal when restated in dimensionless form: $f_{a}^{*}=f_{b}^{*}$ if $q^{*}_{a}=q^{*}_{b}$ and $\tau_{max,a}^{*}=\tau_{max,b}^{*}$ . Furthermore, $f_{b}$ can be obtained from $f_{a}$ or vice versa using the scaling formula given by Equation (35) if this condition is met. However, if $q^{*}_{a}\neq q^{*}_{b}$ or $\tau_{max,a}^{*}\neq\tau_{max,b}^{*}$ , then $f_{a}$ cannot provide us with information on $f_{b}$ without additional assumptions. Figure 7 illustrates that for the pendulum swing-up problem the similarity condition can be represented as a line in a three dimension space created by three dimensional context variables. Each conditions of equal values of $q^{*}$ and $\tau_{max}^{*}$ , is a plane in this space, and the intersection of the two plane is the subset of context meeting the two conditions. Also, it is interesting to note that the fourth context variable $\omega$ is not an additional axis here because it is not involved in eq. (51).

Fig. 7: The dimensionally similar subset (equal $c^{*}$ ) can be represented as a line in a 3D space for the pendulum swing-up problem. The feedback law solutions to problem with context variables on the same line are equivalent in dimensionless form.

#### III-A3 Numerical results

Here, we use a numerical algorithm (methodological details are presented in Section III-A5) to compute numerical solutions to the motion control problem defined by Equations (40), (41), and (42). The algorithm computes feedback laws in the form of look-up tables, based on a discretized grid of the state space. The optimal (up to discretization errors) feedback laws are computed for nine instances of context variables, which are listed in Table III. In those nine contexts, there are three subsets of three dimensionally similar contexts. Also, each subset includes the same three pendulums: a regular pendulum, one that is two times longer, and one that is twice as heavy (as illustrated in Figure 1). Contexts $c_{a}$ , $c_{b}$ , and $c_{c}$ describe a task where the torque is limited to half the maximum gravitational torque. Contexts $c_{d}$ , $c_{e}$ , and $c_{f}$ describe a task where the application of large torques is highly penalized by the cost function. Contexts $c_{g}$ , $c_{h}$ , and $c_{i}$ describe a task where position errors are highly penalized by the cost function.

TABLE III: Pendulum swing-up problem context variables.

| | $m$ | $g$ | $l$ | $q$ | $\tau_{max}$ |
| --- | --- | --- | --- | --- | --- |
| Problems with $\tau_{max}^{*}=0.5$ and $q^{*}=0.1$ | | | | | |
| Context $c_{a}$ : | 1.0 | 10.0 | 1.0 | 1.0 | 5.0 |
| Context $c_{b}$ : | 1.0 | 10.0 | 2.0 | 2.0 | 10.0 |
| Context $c_{c}$ : | 2.0 | 10.0 | 1.0 | 2.0 | 10.0 |
| Problems with $\tau_{max}^{*}=1.0$ and $q^{*}=0.05$ | | | | | |
| Context $c_{d}$ : | 1.0 | 10.0 | 1.0 | 0.5 | 10.0 |
| Context $c_{e}$ : | 1.0 | 10.0 | 2.0 | 1.0 | 20.0 |
| Context $c_{f}$ : | 2.0 | 10.0 | 1.0 | 1.0 | 20.0 |
| Problems with $\tau_{max}^{*}=1.0$ and $q^{*}=10$ | | | | | |
| Context $c_{g}$ : | 1.0 | 10.0 | 1.0 | 100.0 | 10.0 |
| Context $c_{h}$ : | 1.0 | 10.0 | 2.0 | 200.0 | 20.0 |
| Context $c_{i}$ : | 2.0 | 10.0 | 1.0 | 200.0 | 20.0 |

Figures 8 to 16 illustrate that, for each subset with equal dimensionless context, the dimensional feedback laws generated look numerically very similar. They are similar up to the scaling of their axis, if we neglect slight differences due to discretization errors. Furthermore, the figures also illustrate that the dimensionless version of the feedback laws ( $f^{*}$ ), computed using Equation (31), are equal within each dimensionally similar subset. These were the expected results predicted by the dimensional analysis presented in Section II.

Fig. 8: Numerical results for context $c_{a}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 9: Numerical results for context $c_{b}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 10: Numerical results for context $c_{c}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

Fig. 11: Numerical results for context $c_{d}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 12: Numerical results for context $c_{e}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 13: Numerical results for context $c_{f}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 14: Numerical results for context $c_{g}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 15: Numerical results for context $c_{h}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

Fig. 16: Numerical results for context $c_{i}$

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $\theta=-\pi$

.

In terms of how this can be applied in a practical scenario, we see that if we compute the feedback law given in Figure 8(a), we can obtain the feedback law given in Figure 9(a) directly by scaling the original policy with Equation (35), using the appropriate context variables, without having to recompute. In some sense, Equation (35) provides us with the ability to adjust the feedback law spontaneously to conform with new system parameters $mgl$ or $\omega$ , as would be the case with an analytical solution, even when working with black box results in the form of a table look-up. But the equivalence of the scaled solution is only guaranteed within a dimensionally similar context subset, which is the main limitation of this approach. The feedback law given in Figure 8(a) cannot be scaled into the feedback law given in Figure 14(a), for instance, since $\tau^{*}_{max}$ and $q^{*}$ are not equals. It is also interesting to note that trajectory solutions from the same starting point—and computed cost-to-go functions (not illustrated)—are also all equivalent, up to scaling factors, within similar subgroups. Hence, optimal trajectories and cost-to-go solutions could also be shared and transferred between similar systems using the same technique that we demonstrate here for feedback laws.

#### III-A4 Regimes of solutions

In some situations, changing a context variable will not have any effect on the optimal policy. For instance, for a torque-limited optimal pendulum swing-up problem, augmenting $\tau_{max}$ or $q$ while keeping the other value fixed will have little effect above a given threshold. For instance, if we look at the solutions for contexts $c_{d}$ , $c_{e}$ , and $c_{f}$ , using a large amount of torque is so highly penalized by the cost function that the saturation limit does not have much impact on the solution (except for edge cases on the boundary). Thus, we would expect that augmenting $\tau_{max}$ would not change the solution. Figures 17 and 18 show a slice (to allow for visualization) of the dimensionless optimal policy solution for various contexts. Figure 17 illustrates the results of changing $\tau_{max}^{*}$ while keeping $q^{*}$ fixed. We can see that when $\tau_{max}^{*}<0.3$ , the policy is almost always on the min–max allowable torque values; this behavior is often called bang–bang. At the other extreme, when $\tau_{max}^{*}>2.5$ , the policy solution is continuous and almost never affected by the saturation. Figure 18 illustrates the results of changing $q^{*}$ while keeping $\tau_{max}^{*}$ fixed. We can see that when $q^{*}<0.1$ , the optimal policy solution does not reach min–max saturation, while when $q^{*}>1.0$ , the policy is almost always on the min–max allowable values.

Fig. 17: Optimal dimensionless policy for various contexts: $\tau^{*}=\pi^{*}(\theta^{*},\dot{\theta}^{*}=0,q^{*}=0.5,\tau^{*}_{max}=[0.1,...,5.0])$ .

Fig. 18: Optimal dimensionless policy for various contexts: $\tau^{*}=\pi^{*}(\theta^{*},\dot{\theta}^{*}=0,q^{*}=[0.05,...,2.0],\tau^{*}_{max}=0.5).$

Fig. 19: Regime zones for a torque-limited pendulum swing-up problem.

We can see that, for extreme context values, two types of behavior occur, illustrated as regions in the dimensionless context space in Figure 19. Those regions are best characterized by a ratio of $q^{*}$ and $\tau_{max}^{*}$ , a new dimensionless value that we define as the ratio of the maximum torque saturation $\tau_{max}$ over the weight parameter in the cost function $q$ :

| $\displaystyle R^{*}=\frac{\tau^{*}_{max}}{q^{*}}=\frac{\tau_{max}}{q}\quad\quad$ | (53) |
| --- | --- |

When the value of $R^{*}\approx 1$ , the policy solution is partially continuous and reaches the min–max value in some other region of the state space, this is a behavior we call the transition regime. When the value of $R^{*}\ll 1$ , the constraint on torque drives the solution to exhibit bang–bang behavior. In this region (that we approximate here, based on our sensitivity analysis, as $R^{*}\leq 0.1$ ), the global policy is only a function of $\tau_{max}^{*}$ :

| $\displaystyle\pi^{*}(\theta^{*},\dot{\theta}^{*},q^{*},\tau_{max}^{*})$ | $\displaystyle\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},\tau_{max}^{*})\;\text{if}\;R^{*}\ll 1$ | (54) |
| --- | --- | --- |

i.e., the value of $q^{*}$ does not affect the solution. On the other hand, when the value of $R^{*}\gg 1$ , the policy is unconstrained. In this region (that we approximate here, based on our sensitivity analysis, as $R^{*}\geq 10$ ), the global policy is only a function of $q^{*}$ since the constraint is so far away:

| $\displaystyle\pi^{*}(\theta^{*},\dot{\theta}^{*},q^{*},\tau_{max}^{*})$ | $\displaystyle\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},q^{*})\;\text{if}\;R^{*}\gg 1$ | (55) |
| --- | --- | --- |

The concept of regime is often leveraged in fluid mechanics. It allows us to generalize results between situations where the relevant dimensionless numbers do not match exactly. For instance, when the Mach number is small ( $Ma<0.3$ ), we can generally assume there to be in an incompressible regime where various speeds of sound would not change the behavior much. Here, for the purpose of transferring policy solutions between contexts, this means that the condition of having the same exact dimensionless context variables can be relaxed with an inequality that corresponds to a regime. For instance, if we have two contexts in the unconstrained regime, it is sufficient to match only $q^{*}$ to create equivalent dimensionless policies.

###### Proposition 1

If it is assumed that Equation (55) holds, the condition of having equivalent dimensionless feedback laws is relaxed to an inequality for one of the context variables, as follows:

| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})\approx f_{b}^{*}(\theta^{*},\dot{\theta}^{*})$ | (56) |
| --- | --- |
| $\displaystyle\text{if}\quad q^{*}_{a}=q^{*}_{b}\quad\text{{and}}\quad R^{*}_{a}\gg 1\quad\text{{and}}\quad R^{*}_{b}\gg 1$ | (57) |

###### Proof:

First, if $R_{a}^{*}\gg 1$ and $R_{b}^{*}\gg 1$ then from Equation (55) we can approximate the policy not to be a function of $\tau_{max}^{*}$ :

| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle=\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{a}^{*},\tau_{max,a}^{*})\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{a}^{*})$ | (58) |
| --- | --- | --- |
| $\displaystyle f_{b}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle=\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{b}^{*},\tau_{max,b}^{*})\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{b}^{*})$ | (59) |

Hence, if $q_{a}^{*}=q_{b}^{*}$ we have:

| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{a}^{*})=\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{b}^{*})\approx f_{b}^{*}(\theta^{*},\dot{\theta}^{*})$ | (60) |
| --- | --- |

∎Also, for two contexts in a bang–bang regime, it is sufficient to match only $\tau_{max}^{*}$ to have equivalent dimensionless policies.

###### Proposition 2

If it is assumed that Equation (54) holds, the condition of having equivalent dimensionless feedback laws is relaxed to an inequality for one of the context variables, as follows:

| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})\approx f_{b}^{*}(\theta^{*},\dot{\theta}^{*})$ | (61) |
| --- | --- |
| $\displaystyle\text{if}\quad\tau^{*}_{max,a}=\tau^{*}_{max,b}\quad\text{{and}}\quad R^{*}_{a}\ll 1\quad\text{{and}}\quad R^{*}_{b}\ll 1$ | (62) |

###### Proof:

First, if $R_{a}^{*}\ll 1$ and $R_{b}^{*}\ll 1$ then from Equation (54) we can approximate the policy not to be a function of $q^{*}$ :

| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle=\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{a}^{*},\tau_{max,a}^{*})\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},\tau^{*}_{max,a})$ | (63) |
| --- | --- | --- |
| $\displaystyle f_{b}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle=\pi^{*}(\theta^{*},\dot{\theta}^{*},q_{b}^{*},\tau_{max,b}^{*})\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},\tau^{*}_{max,b})$ | (64) |

Hence, if $\tau^{*}_{max,a}=\tau^{*}_{max,a}$ we have:

| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},\tau^{*}_{max,a})$ | (65) |
| --- | --- | --- |
| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle\approx\pi^{*}(\theta^{*},\dot{\theta}^{*},\tau^{*}_{max,b})$ | (66) |
| $\displaystyle f_{a}^{*}(\theta^{*},\dot{\theta}^{*})$ | $\displaystyle\approx f_{b}^{*}(\theta^{*},\dot{\theta}^{*})$ | (67) |

∎

From another point of view, assuming that one of those regimes applies means that we could have removed one variable from the context at the start of the dimensional analysis. All in all, the impact of identifying such regimes is that we can increase the size of the context subset to which the dimensionless version of the policy should be equivalent, leading to a potentially larger pool of systems that can share a learned policy and numerical results.

#### III-A5 Methodology

We obtained the optimal feedback law presented in this section using a basic dynamic programming algorithm [18] on a discretized version of the continuous system. The approach is almost equivalent to the value iteration algorithm [5]—which is sometimes referred to as model-based reinforcement learning—with the exception that, here, the total number of iteration steps was fixed (corresponding to a very long time horizon approximating an infinite horizon), instead of the iteration being stopped after reaching a convergence criterion. This approach was chosen to enable the collection of consistent results across all contexts that lead to a wide range of order-of-magnitude cost-to-go solutions. The time step was set to 0.025 s, the state space was discretized into an even 501 x 501 grid, and the continuous torque input was discretized into 101 discrete control options. Special out-of-bounds and on-target termination states were included to guarantee convergence [18]. Also, using dynamic programming made the setting of additional parameters to define the domain necessary. Although those parameters should not affect the optimal policy far away from the boundaries, dimensionless versions of those parameters were kept fixed in all the experiments, as follows:

| $\displaystyle\theta^{*}_{max}$ | $\displaystyle=\theta_{max}=2\pi$ | (68) |
| --- | --- | --- |
| $\displaystyle\dot{\theta}^{*}_{max}$ | $\displaystyle=\frac{\dot{\theta}_{max}}{\omega}=\pi$ | (69) |
| $\displaystyle t^{*}_{f}$ | $\displaystyle=t_{f}\;\omega=20\times 2\pi$ | (70) |

where $\theta_{max}$ is the range of angles for which the optimal policy is solved, set to one full revolution; $\dot{\theta}_{max}$ is the range of angular velocity for which the optimal policy is solved; and $t_{f}$ is the time horizon, set to 20 periods of the pendulum using the natural frequency. The source code is available online at the following link: https://github.com/alx87grd/DimensionlessPolicies, and this Google Colab page allows users to reproduce the results: https://colab.research.google.com/drive/1kf3apyHlf5t7XzJ3uVM8mgDsneVK_63r?usp=sharing.

### III-B Optimal motion for a longitudinal car on a slippery surface

The second numerical example is a simplified car positioning task. We use this example to illustrate that an optimal feedback law in the form of a table look-up generated for a car of a given size, can be transferred to a car of a different size if the motion control problem is dimensionally similar. The example includes state constraints and a different type of non-linearity (i.e. is its not similar to the pendulum swing-up) to illustrate how generic the developed dimensionless polices concept are.

Fig. 20: Car positioning motion control problem.

#### III-B1 Motion control problem

The motion control problem is defined here as finding a feedback law to control the dynamic system, as described by the following differential equation:

| $$\ddot{x}=\frac{\mu(s)gx_{c}}{l+\mu(s)y_{c}}\quad\quad\text{with}\quad\quad\mu(s)=\frac{f_{x}}{f_{n}^{f}}=\frac{2}{1+e^{-70s}}-1$$ | (71) |
| --- | --- |

where $\mu(s)$ is the ratio of vertical to horizontal forces on the front wheel, that is, a non-linear function of the front wheel slip $s$ . The above equations represent a simple dynamic model of the longitudinal motion of a car, assuming that the controller can impose the wheel slip of the front wheel and that suspensions are infinitely rigid (but that weight transfer is included). Interestingly, it is already standard practice to model the ground–tire interaction with an empirical curve $\mu(s)$ relating two dimensionless variables.

The objective is to minimize the infinite horizon quadratic cost function given by:

| $$J=\int_{0}^{\infty}{\left(q^{-2}x^{2}+\,s^{2}\right)dt}$$ | (72) |
| --- | --- |

subject to the constraints of keeping ground reaction forces positive, as given by:

| $\displaystyle 0\leq$ | $\displaystyle f_{n}^{f}=gx_{c}-\ddot{x}y_{c}$ | (73) |
| --- | --- | --- |
| $\displaystyle 0\leq$ | $\displaystyle f_{n}^{r}=g(l-x_{c})+\ddot{x}y_{c}$ | (74) |

where the weight transfer potentially limits the allowable motions. Note that the cost function parameter $q$ in this problem has a power of minus two to have a value with units of length, and all parameters are time-independent constants. The solution to this problem, i.e., the optimal policy for all contexts, involves the variables listed in Table IV and should be of the form given by:

| $$\underbrace{s}_{\text{input}}=\pi\left(\underbrace{x,\dot{x}}_{\text{states}},\underbrace{x_{c},y_{c},g,l,q}_{\text{Context $c$}}\right)$$ | (75) |
| --- | --- |

.

TABLE IV: Longitudinal car optimal policy variables

. Variable Description Units Dimensions Control inputs $s$ Wheel slip - [] State variables $x$ Car position $m$ [L] $\dot{x}$ Car velocity $m/sec$ [ $LT^{-1}$ ] System parameters $g$ Gravity $m/s^{2}$ [ $LT^{-2}$ ] $l$ Length (wheel base) $m$ [ $L$ ] $x_{c}$ center of gravity (CG) horizontal position $m$ [ $L$ ] $y_{c}$ center of gravity (CG) vertical position $m$ [ $L$ ] Problem parameters $q$ Weight parameter $m$ [ $L$ ]

#### III-B2 Dimensional analysis

Here, we have one control input, two states, and five context parameters, for a total of $1+(n=2)+(m=5)=8$ variables. Of those variables, only $d=2$ independent dimensions (length $[L]$ and time $[T]$ ) are present. Using $c_{1}=g$ and $c_{2}=l$ as the repeated variables leads to the following dimensionless groups:

| $\displaystyle\Pi_{1}$ | $\displaystyle=s^{*}=s\quad\quad[]$ | (76) |
| --- | --- | --- |
| $\displaystyle\Pi_{2}$ | $\displaystyle=x^{*}=\frac{x}{l}\quad\quad\frac{[L]}{[L]}$ | (77) |
| $\displaystyle\Pi_{3}$ | $\displaystyle=\dot{x}^{*}=\frac{\dot{x}}{\sqrt{gl}}\quad\quad\frac{[LT^{-1}]}{[LT^{-2}]^{1/2}[L]^{1/2}}$ | (78) |
| $\displaystyle\Pi_{4}$ | $\displaystyle=x_{c}^{*}=\frac{x_{c}}{l}\quad\quad\frac{[L]}{[L]}$ | (79) |
| $\displaystyle\Pi_{5}$ | $\displaystyle=y_{c}^{*}=\frac{y_{c}}{l}\quad\quad\frac{[L]}{[L]}$ | (80) |
| $\displaystyle\Pi_{6}$ | $\displaystyle=q^{*}=\frac{q}{l}\quad\quad\frac{[L]}{[L]}$ | (81) |

All three length variables are scaled by the wheel base, and the velocity variable is scaled using a combination of the wheel base and gravity. The transformation matrices are then as follows:

| $\displaystyle s*$ | $\displaystyle=\underbrace{\left[1\right]}_{T_{u}}\,s$ | (82) |
| --- | --- | --- |
| $\displaystyle\begin{bmatrix}x^{*}\\ \dot{x}^{*}\end{bmatrix}$ | $\displaystyle=\underbrace{\begin{bmatrix}\frac{1}{l}&0\\ 0&\frac{1}{\sqrt{gl}}\end{bmatrix}}_{T_{x}}\,\begin{bmatrix}x\\ \dot{x}\end{bmatrix}$ | (83) |
| $\displaystyle\underbrace{\begin{bmatrix}x_{c}^{*}\\ y_{c}^{*}\\ q^{*}\end{bmatrix}}_{c^{*}}$ | $\displaystyle=\underbrace{\begin{bmatrix}0&0&1/l&0&0\\ 0&0&0&1/l&0\\ 0&0&0&0&1/l\end{bmatrix}}_{T_{c}}\,\underbrace{\begin{bmatrix}g\\ l\\ x_{c}\\ y_{c}\\ q\end{bmatrix}}_{c}$ | (84) |

By applying the Buckingham $\pi$ theorem [4], Equation (75) can be restated as a relationship between the six dimensionless $\Pi$ groups, as follows:

| $$s^{*}=\pi^{*}\left(x^{*},\dot{x}^{*},x_{c}^{*},y_{c}^{*},q^{*}\right)$$ | (85) |
| --- | --- |

#### III-B3 Numerical results

Here, as in the pendulum example, numerical solutions to the motion control problem are computed for the nine instances of context variables listed in Table V. In those nine contexts, there are three subsets of three dimensionally similar contexts. Contexts $c_{a}$ , $c_{b}$ , and $c_{c}$ describe situations where the CG. horizontal position is at half the wheel base; contexts $c_{d}$ , $c_{e}$ and $c_{f}$ describe situations in which the the CG is very high (and hence the cars are very limited by the weight transfer); and contexts $c_{h}$ , $c_{i}$ , and $c_{j}$ describe situations in which position errors are highly penalized by the cost function plus cars with a very low CG relative to the wheel base.

TABLE V: Car problem parameters.

| | $l$ | $g$ | $x_{c}$ | $y_{c}$ | $q$ |
| --- | --- | --- | --- | --- | --- |
| Problems with $x_{c}^{*}=0.5$ , $y_{c}^{*}=0.5$ , and $q^{*}=20$ | | | | | |
| Context $c_{a}$ : | 2.0 | 9.8 | 1.0 | 1.0 | 40 |
| Context $c_{b}$ : | 1.0 | 9.8 | 0.5 | 0.5 | 20 |
| Context $c_{c}$ : | 3.0 | 9.8 | 1.5 | 1.5 | 60 |
| Problems with $x_{c}^{*}=0.5$ , $y_{c}^{*}=1.5$ , and $q^{*}=10$ | | | | | |
| Context $c_{d}$ : | 2.0 | 9.8 | 1.0 | 3.0 | 20 |
| Context $c_{e}$ : | 1.0 | 9.8 | 0.5 | 1.5 | 10 |
| Context $c_{f}$ : | 3.0 | 9.8 | 1.5 | 4.5 | 30 |
| Problems with $x_{c}^{*}=0.5$ , $y_{c}^{*}=0.1$ , and $q^{*}=2$ | | | | | |
| Context $c_{g}$ : | 2.0 | 9.8 | 1.0 | 0.2 | 4 |
| Context $c_{h}$ : | 1.0 | 9.8 | 0.5 | 0.1 | 2 |
| Context $c_{i}$ : | 3.0 | 9.8 | 1.5 | 0.3 | 6 |

Figures 21 to 29 illustrate that, for each subset with an equal dimensionless context, solutions are equal within each dimensionally similar subset when scaled into the dimensionless form. This was, again, the expected result predicted by the dimensional analysis presented in Section II. In terms of how to use this in a practical scenario, this exemplifies how various cars (which are different but which share the same ratios) could share a braking policy, for instance.

Fig. 21: Numerical results for context $c_{a}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 22: Numerical results for context $c_{b}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 23: Numerical results for context $c_{c}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 24: Numerical results for context $c_{d}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 25: Numerical results for context $c_{e}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 26: Numerical results for context $c_{f}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 27: Numerical results for context $c_{g}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 28: Numerical results for context $c_{h}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

Fig. 29: Numerical results for context $c_{i}$ .

(a) Feedback law $f$

(b) Dimensionless feedback law $f^{*}$

(c) Optimal trajectory, starting at $x=-5l$

#### III-B4 Methodology

The same methodology as the pendulum example (see Section III-A5) was used for the car motion control problem. The time step was set to 0.025 s, the state space was discretized into an even 501 x 501 grid, and the continuous slip input was discretized into 101 discrete control options. Additional domain parameters were set as follows:

| $\displaystyle x_{max}$ | $\displaystyle=10l$ | (86) |
| --- | --- | --- |
| $\displaystyle\dot{x}_{max}$ | $\displaystyle=\frac{2}{\sqrt{gl}}$ | (87) |
| $\displaystyle t_{max}$ | $\displaystyle=10\frac{x_{max}}{v_{max}}$ | (88) |

The source code is available online at the following link: https://github.com/alx87grd/DimensionlessPolicies, and this Google Colab page allows users to reproduce the results: https://colab.research.google.com/drive/1-CSiLKiNLqq9JC3EFLqjR1fRdICI7e7M?usp=share_link.

## IV Case studies with closed-form parametric policies

To better understand the concept of a dimensionless policy, in this section two examples based on well-known closed-form solutions to classical motion control problems are presented to illustrate how using Theorem 2 can be equivalent to substituting new system parameters in an analytical solution.

### IV-A Dimensionless linear quadratic regulator

The first example is based on the linear quadratic regulator (LQR) solution [19] for the linearized pendulum that allows for a closed-form analytical solution of optimal policy. This allow us to compared the method of transferring the policy with the proposed scaling law of Equation (35), to the method of transferring the policy by substituting the new system parameters in the analytical solution.

Here, we consider a simplified version of the pendulum swing-up problem (see Section III-A) and a linearized version of the equation of motion is used, as follows:

| $$ml^{2}\ddot{\theta}-mgl\theta=\tau$$ | (89) |
| --- | --- |

The same infinite horizon quadratic cost function is used, as follows:

| $$J=\int_{0}^{\infty}{\left(q^{2}\theta^{2}+\,\tau^{2}\right)dt}$$ | (90) |
| --- | --- |

However, no constraints on the torque are included in this problem. All parameters are also assumed to be time-independent constant. The same variables are used in this problem definition as before, except that the torque limit $\tau_{max}$ variable is absent. The global policy solution should then have the following form:

| $$\underbrace{\tau}_{\text{inputs}}=\pi_{lqr}\left(\underbrace{\theta,\dot{\theta}}_{\text{states}},\underbrace{\underbrace{m,g,l}_{\text{system parameters}},\underbrace{q}_{\text{task parameters}}}_{\text{context $c$}}\right)$$ | (91) |
| --- | --- |

We can thus select the same dimensionless $\Pi$ groups as in Section III-A2 and conclude that Equation (91) can be restated under the following dimensionless form:

| $$\tau^{*}=\pi^{*}_{lqr}\left(\theta^{*},\dot{\theta}^{*},q^{*}\right)$$ | (92) |
| --- | --- |

###### Proposition 3

For this motion control problem, defined by Equation (89) and Equation (90), an analytical solution exists and the optimal policy is given by:

| $\displaystyle\tau$ | $\displaystyle=\Biggl[mgl+\sqrt{(mgl)^{2}+q^{2}}\Biggr]\theta$ |
| --- | --- |
| | $\displaystyle+\Biggl[\sqrt{2ml^{2}\Bigl(mgl+\sqrt{(mgl)^{2}+q^{2}}}\Bigr)\Biggr]\dot{\theta}$ | (93) |

###### Proof:

See Appendix.∎

Applying Equation (31) to this feedback law leads to the dimensionless form, using $G=mgl$ and $H=ml^{2}$ for shortness, as follows:

| $\displaystyle\tau^{*}$ | $\displaystyle=f^{*}(x^{*})=\left[T_{u}(c)\right]f\left(\left[T_{x}^{-1}(c)\right]\;x^{*}\right)=\frac{1}{G}f(\theta^{*},\omega\dot{\theta}^{*})$ | (94) |
| --- | --- | --- |
| $\displaystyle\tau^{*}$ | $\displaystyle=\left[\frac{1}{G}\right]\left[G+\sqrt{G^{2}+q^{2}}\right]\theta^{*}$ |
| | $\displaystyle+\left[\frac{1}{G}\right]\left[\sqrt{2H\left(G+\sqrt{G^{2}+q^{2}}\right)}\right]\left[\omega\dot{\theta}^{*}\right]$ | (95) |
| $\displaystyle\tau^{*}$ | $\displaystyle=\left[1+\sqrt{\frac{G^{2}+q^{2}}{G^{2}}}\right]\theta^{*}$ |
| | $\displaystyle+\left[\sqrt{\frac{2H\omega^{2}}{G}\frac{G+\sqrt{G^{2}+q^{2}}}{G}}\right]\dot{\theta}^{*}$ | (96) |
| $\displaystyle\tau^{*}$ | $\displaystyle=\left[1+\sqrt{1+(q^{*})^{2}}\right]\theta^{*}+\left[\sqrt{2}\sqrt{1+\sqrt{1+(q^{*})^{2}}}\right]\dot{\theta}^{*}$ | (97) |

The dimensionless policy is only a function of the dimensionless states and the dimensionless cost parameter $q^{*}$ , as predicted by Equation (92) based on the dimensional analysis. It is interesting to note that Equation (97) represents the core generic solution to the LQR problem and is independent of unit and scale.

We can also use this analytical policy solution to demonstrate Theorem 2, i.e. show that scaling the policy with Equation (35) is equivalent to substituting new context variables when the contexts are dimensionally similar.

###### Proposition 4

Suppose that we have two context instances, labeled $a$ and $b$ , and that we use the global policy solution of Equation (93) to obtain two versions of context-specific feedback laws:

| $\displaystyle f_{a}(\theta,\dot{\theta})$ | $\displaystyle=\left[G_{a}+\sqrt{G_{a}^{2}+q_{a}^{2}}\right]\theta$ |
| --- | --- |
| | $\displaystyle+\left[\sqrt{2H_{a}(G_{a}+\sqrt{G_{a}^{2}+q_{a}^{2}})}\right]\dot{\theta}$ | (98) |
| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=\left[G_{b}+\sqrt{G_{b}^{2}+q_{b}^{2}}\right]\theta$ |
| | $\displaystyle+\left[\sqrt{2H_{b}(G_{b}+\sqrt{G_{b}^{2}+q_{b}^{2}})}\right]\dot{\theta}$ | (99) |

where

| $\displaystyle G_{a}=m_{a}g_{a}l_{a}\quad H_{a}=m_{a}l_{a}^{2}$ | (100) |
| --- | --- |
| $\displaystyle G_{b}=m_{b}g_{b}l_{b}\quad H_{b}=m_{b}l_{b}^{2}$ | (101) |

Based on Theorem 2, if $q_{a}^{*}=q_{b}^{*}$ we can obtain $f_{b}$ directly by scaling $f_{a}$ based on Equation (35) as follow:

| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=\left[\frac{G_{b}}{G_{a}}\right]f_{a}\left(\theta,\left[\frac{\omega_{a}}{\omega_{b}}\right]\dot{\theta}\right)$ | (102) |
| --- | --- | --- |

where

| $\displaystyle\omega_{a}=\sqrt{G_{a}/H_{a}}\quad\omega_{b}=\sqrt{G_{b}/H_{b}}$ | (103) |
| --- | --- |

###### Proof:

If we substitute $f_{a}$ in Equation (102) by the analytical solution given by Equation (98), and then distribute the multiplying scaling factors we obtain:

| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=\left[\frac{G_{b}}{G_{a}}\right]\Biggl(\left[G_{a}+\sqrt{G_{a}^{2}+q_{a}^{2}}\right]\theta$ |
| --- | --- |
| | $\displaystyle+\left[\sqrt{2H_{a}(G_{a}+\sqrt{G_{a}^{2}+q_{a}^{2}})}\right]\left[\frac{\omega_{a}}{\omega_{b}}\right]\dot{\theta}\Biggr)$ | (104) |
| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=G_{b}\left[1+\sqrt{1+(q_{a}^{*})^{2}}\right]\theta$ |
| | $\displaystyle+G_{b}\left[\sqrt{2}\sqrt{1+\sqrt{1+(q_{a}^{*})^{2}}}\right]\frac{\dot{\theta}}{\omega_{b}}$ | (105) |
| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=\left[G_{b}+\sqrt{G_{b}^{2}+(G_{b}q_{a}^{*})^{2}}\right]\theta$ |
| | $\displaystyle+\left[\sqrt{2H_{b}}\sqrt{G_{b}+\sqrt{G_{b}^{2}+(G_{b}q_{a}^{*})^{2}}}\right]\dot{\theta}$ | (106) |

which is equivalent to Equation (99) when

| $\displaystyle G_{b}q_{a}^{*}=q_{b}\quad\text{or equivalently }\quad q_{a}^{*}=q_{b}^{*}$ | (107) |
| --- | --- |

which is the condition of having equal dimensionless contexts ( $c_{a}^{*}=c_{b}^{*}$ ) for this motion control problem. ∎

This example illustrates that applying the scaling of Equation (35) based on the dimensional analysis framework is equivalent to changing the context variables in an analytical solution when the dimensionless context variables are equal.

### IV-B Dimensionless computed torque

The second example is again based on the pendulum, but using the computed torque control technique [20]. This also allow us to compared the method of transferring the policy with the proposed scaling law of Equation (35), to the method of transferring the policy by substituting the new system parameters in the analytical solution. This example is not based on a quadratic cost function, as opposed to previous examples, to illustrate the flexibility of the proposed schemes.

Here, we present a second analytical example, A computed torque feedback law is a model-based policy (assuming that there are no torque limits) that is the solution to the motion control problem of making a mechanical system that converges on a desired trajectory, with a specified second-order exponential time profile defined by the following equation:

| $$0=(\ddot{\theta}_{d}-\ddot{\theta})+2\omega_{d}\zeta(\dot{\theta}_{d}-\dot{\theta})+\omega_{d}^{2}(\theta-\theta)$$ | (108) |
| --- | --- |

For the specific case of the pendulum-swing up problem, we assume that all parameters are time-independent constants and that our desired trajectory is simply the upright position ( $\ddot{\theta}_{d}=\dot{\theta}_{d}=\theta_{d}=0$ ), leaving only two parameters to define the tasks: $\omega_{d}$ and $\zeta$ . Then, the computed torque policy takes the following form:

| $\displaystyle\underbrace{\tau}_{\text{input}}$ | $\displaystyle=\pi_{ct}\left(\underbrace{\theta,\dot{\theta}}_{\text{states}},\underbrace{\underbrace{m,g,l}_{\text{system parameters}},\underbrace{\omega_{d},\zeta}_{\text{task parameters}}}_{\text{context $c$}}\right)$ | (109) |
| --- | --- | --- |

and the analytical solution is as follows:

| $\displaystyle\tau$ | $\displaystyle=mgl\sin\theta-2ml^{2}\omega_{d}\zeta\dot{\theta}-ml^{2}\omega_{d}^{2}\theta$ | (110) |
| --- | --- | --- |

Here, the context includes the system parameters and two variables characterizing the convergence speed. Note that the task parameters directly define the desired behavior, as opposed to the previous examples where they were defining the behavior indirectly thought a cost function. The states, control inputs, and system parameters are the same as before; only the task parameters differ, and their dimensions are presented in Table VI.

TABLE VI: Computed torque task variables.

| Variable | Description | Units | Dimensions |
| --- | --- | --- | --- |
| Task parameters | | | |
| $\omega_{d}$ | Desired closed-loop frequency | $s^{-1}$ | [ $T^{-1}$ ] |
| $\zeta$ | Desired closed-loop damping | $-$ | [-] |

Here, seven variables and only $p=2$ independent dimensions ( $ML^{2}T^{-2}$ and $T^{-1}$ ) are involved. Thus, five dimensionless groups can be formed, as follows:

| $$1+(n=2)+(m=4)-(p=2)=5$$ | (111) |
| --- | --- |

Using $mgl$ and $\omega$ , the system parameters, as the repeating variables leads to the following dimensionless groups:

| $\displaystyle\Pi_{1}$ | $\displaystyle=\tau^{*}=\frac{\tau}{mgl}\quad\quad\frac{[ML^{2}T^{-2}]}{[M][LT^{-2}][L]}$ | (112) |
| --- | --- | --- |
| $\displaystyle\Pi_{2}$ | $\displaystyle=\theta^{*}=\theta\quad\quad[-]$ | (113) |
| $\displaystyle\Pi_{3}$ | $\displaystyle=\dot{\theta}^{*}=\frac{\dot{\theta}}{\omega}\quad\quad\frac{[T^{-1}]}{[T^{-1}]}$ | (114) |
| $\displaystyle\Pi_{4}$ | $\displaystyle=\omega_{d}^{*}=\frac{\omega_{d}}{\omega}\quad\quad\frac{[T^{-1}]}{[T^{-1}]}$ | (115) |
| $\displaystyle\Pi_{5}$ | $\displaystyle=\zeta^{*}=\zeta\quad\quad[-]$ | (116) |

Then, applying the Buckingham $\pi$ theorem tells us that the computed torque policy can be restated as the following relationship between the dimensionless variables:

| $$\tau^{*}=\pi^{*}_{ct}\left(\theta,\dot{\theta}^{*},\omega_{d}^{*},\zeta^{*}\right)$$ | (117) |
| --- | --- |

Here, we can confirm directly (since we have an analytical solution) that applying Equation (31) to the computed torque feedback law given by Equation (110) leads to the following dimensionless form:

| $\displaystyle\tau^{*}$ | $\displaystyle=\left[\frac{1}{mgl}\right]\left(mgl\sin\theta-2ml^{2}\omega_{d}\zeta\left(\omega\dot{\theta}^{*}\right)-ml^{2}\omega_{d}^{2}\theta\right)$ | (118) |
| --- | --- | --- |
| $\displaystyle\tau^{*}$ | $\displaystyle=\sin\theta^{*}-2\omega_{d}^{*}\zeta^{*}\dot{\theta}^{*}-(\omega_{d}^{*})^{2}\theta^{*}$ | (119) |

thereby confirming the structure predicted by Equation (117) based on the dimensional analysis.

We can, again, use this example to demonstrate Theorem 2 and show that, when the dimensionless context is equal, scaling a policy using Equation (35) is equivalent to substituting new values of the system parameters into the analytical equation.

###### Proposition 5

Suppose that we have two context instances, labeled $a$ and $b$ , and that we use the global policy solution of Equation (110) to obtain two versions of context-specific feedback laws:

| $\displaystyle f_{a}(\theta,\dot{\theta})$ | $\displaystyle=G_{a}\sin\theta-2H_{a}\omega_{d,a}\zeta_{a}\dot{\theta}-H_{a}\omega_{d,a}^{2}\theta$ | (120) |
| --- | --- | --- |
| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=G_{b}\sin\theta-2H_{b}\omega_{d,a}\zeta_{b}\dot{\theta}-H_{b}\omega_{d,a}^{2}\theta$ | (121) |

Based on Theorem 2, if $\omega^{*}_{d,a}=\omega^{*}_{d,b}$ and $\zeta_{a}^{*}=\zeta_{b}^{*}$ we can obtain $f_{b}$ directly by scaling $f_{a}$ based on Equation (35) as follow:

| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=\left[\frac{G_{b}}{G_{a}}\right]f_{a}\left(\theta,\left[\frac{\omega_{a}}{\omega_{b}}\right]\dot{\theta}\right)$ | (122) |
| --- | --- | --- |

###### Proof:

If we substitute $f_{a}$ in Equation (122) by the analytical solution given by Equation (120), and then distribute the multiplying scaling factors we obtain:

| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=\left[\frac{G_{b}}{G_{a}}\right]\Bigr[G_{a}\sin\theta-2H_{a}\omega_{d,a}\zeta_{a}\left[\frac{\omega_{a}}{\omega_{b}}\right]\dot{\theta}$ |
| --- | --- |
| | $\displaystyle-H_{a}\omega_{d,a}^{2}\theta\Bigl]$ | (123) |
| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=G_{b}\left[\sin\theta-2\frac{\omega_{d,a}}{\omega_{a}}\zeta_{a}\frac{\dot{\theta}}{\omega_{b}}-\left(\frac{\omega_{d,a}}{\omega_{a}}\right)^{2}\theta\right]$ | (124) |
| $\displaystyle f_{b}(\theta,\dot{\theta})$ | $\displaystyle=G_{b}\sin\theta-2H_{b}\left(\frac{\omega_{b}}{\omega_{a}}\omega_{d,a}\right)\zeta_{a}\dot{\theta}$ |
| | $\displaystyle-H_{b}\left(\frac{\omega_{b}}{\omega_{a}}\omega_{d,a}\right)^{2}\theta$ | (125) |

which is exactly equivalent to Equation (121) (i.e., equivalent to substituting the $a$ instance of the context variables to the $b$ instance) if:

| $\displaystyle\frac{\omega_{b}}{\omega_{a}}\omega_{d,a}=\omega_{d,b}\quad\text{and}\quad\zeta_{a}=\zeta_{b}$ | (126) |
| --- | --- |

which is the dimensional similarity condition ( $c_{a}^{*}=c_{b}^{*}$ ) for this motion control problem:

| $\displaystyle\frac{\omega_{d,a}}{\omega_{a}}=\omega^{*}_{a}=\omega^{*}_{b}=\frac{\omega_{d,b}}{\omega_{b}}\quad\text{and}\quad\zeta_{a}^{*}=\zeta_{b}^{*}$ | (127) |
| --- | --- |

∎

## V Conclusion

The dimensional analysis of physically meaningful control policies, leveraging the Buckingham $\pi$ theorem, leads to two interesting theoretical results: 1) In dimensionless form, the solution to a motion control problem involves a reduced number of parameters. 2) It is possible to exactly transfer a feedback law between similar systems without any approximation, simply by scaling the input and output of any type of control law appropriately, including via numerically generated black box mapping. However, the main practical limitation of this approach is that if the condition of dimensional similarity ( $c_{a}^{*}=c_{b}^{*}$ ) is not met exactly, then there is no theoretical guarantees regarding whether a policy is transferable without additional assumptions, as the discussed concept of regimes of behaviour. Also, we demonstrated how those results can be used to transfer exactly even discontinuous black-box policies between similar systems, using two simple examples of dynamical systems and numerically generated optimal feedback laws. An interesting direction for further exploration would be investigating how good an approximation is when a feedback law is transferred from a context that is not exactly similar but close. Also, it would be interesting to test the concept of dimensionless policies to empower a reinforcement learning scheme that could collect data from various, but dimensionally similar, systems to accelerate the learning process.

In this section, we show that the policy given by Equation (93) is optimal with respect to the LQR problem defined in Section IV-A. We can write the equation of motion given by Equation (89) in state-space form, using $G=mgl$ and $H=ml^{2}$ , as follows:

| $$\frac{d}{dt}\begin{bmatrix}\theta\\ \dot{\theta}\end{bmatrix}=\underbrace{\begin{bmatrix}0&1\\ G/H&0\end{bmatrix}}_{A}\underbrace{\begin{bmatrix}\theta\\ \dot{\theta}\end{bmatrix}}_{x}+\underbrace{\begin{bmatrix}0\\ 1/H\end{bmatrix}}_{B}\underbrace{\begin{bmatrix}\tau\end{bmatrix}}_{u}$$ | (128) |
| --- | --- |

Then, by adapting a solution from [21], if we parameterize the weight matrix of the cost function as follows:

| $$J=\int_{0}^{\infty}{\left(x^{T}\underbrace{\begin{bmatrix}a(a-2G)&0\\ 0&b^{2}-2aH\end{bmatrix}}_{Q}x+u^{T}\underbrace{\begin{bmatrix}1\end{bmatrix}}_{R}u\right)dt}$$ | (129) |
| --- | --- |

the optimal cost-to-go is given by:

| $$J=x^{T}\underbrace{\begin{bmatrix}b(a-G)&aH\\ aH&bH\end{bmatrix}}_{S}x$$ | (130) |
| --- | --- |

and the optimal feedback policy is given by:

| $$u=-\underbrace{\left[R^{-1}B^{T}S\right]}_{K}x=-\underbrace{\begin{bmatrix}a&b\\ \end{bmatrix}}_{K}x$$ | (131) |
| --- | --- |

This solution can by verified by substituting matrices into the algebraic Riccati equation given by:

| $$0=SA+A^{T}S-SBR^{-1}B^{T}S+Q$$ | (132) |
| --- | --- |

since the problem fits into the framework of the classical infinite horizon LQR result [18]. Then, we can see that the cost function defined in Section IV-A is a special case, where $Q_{11}=q^{2}$ and $Q_{22}=0$ , leading to the following equations:

| $\displaystyle q^{2}$ | $\displaystyle=a(a-2G)$ | (133) |
| --- | --- | --- |
| $\displaystyle 0$ | $\displaystyle=b^{2}-2aH$ | (134) |

Solving for $a$ and $b$ , and retaining the positive solution, leads to the following:

| $\displaystyle a$ | $\displaystyle=G+\sqrt{G^{2}+q^{2}}$ | (135) |
| --- | --- | --- |
| $\displaystyle b$ | $\displaystyle=\sqrt{2aH}=\sqrt{2H\left(G+\sqrt{G^{2}+q^{2}}\right)}$ | (136) |

which, when substituted into Equation (131), is equal to the policy given by Equation (93) in Section IV-A.

## References

- [1] S. Kuindersma, R. Deits, M. Fallon, A. Valenzuela, H. Dai, F. Permenter, T. Koolen, P. Marion, and R. Tedrake, “Optimization-based locomotion planning, estimation, and control design for the atlas humanoid robot,” Autonomous Robots, vol. 40, no. 3, pp. 429–455, Mar. 2016. [Online]. Available: https://doi.org/10.1007/s10514-015-9479-3
- [2] M. Schwenzer, M. Ay, T. Bergs, and D. Abel, “Review on model predictive control: an engineering perspective,” The International Journal of Advanced Manufacturing Technology, vol. 117, no. 5, pp. 1327–1349, Nov. 2021. [Online]. Available: https://doi.org/10.1007/s00170-021-07682-3
- [3] N. Rudin, D. Hoeller, P. Reist, and M. Hutter, “Learning to Walk in Minutes Using Massively Parallel Deep Reinforcement Learning,” in Proceedings of the 5th Conference on Robot Learning. PMLR, Jan. 2022, pp. 91–100, iSSN: 2640-3498. [Online]. Available: https://proceedings.mlr.press/v164/rudin22a.html
- [4] M. E. Buckingham, “On Physically Similar Systems; Illustrations of the Use of Dimensional Equations,” Physical Review, Oct. 1914, publisher: American Physical Society (APS). [Online]. Available: https://www.scienceopen.com/document?vid=805fe995-1849-413a-b228-3fe616732290
- [5] R. S. Sutton and A. G. Barto, Reinforcement Learning, second edition: An Introduction, second edition ed. Cambridge, Massachusetts: Bradford Books, Nov. 2018.
- [6] M. E. Taylor and P. Stone, “Transfer Learning for Reinforcement Learning Domains: A Survey,” The Journal of Machine Learning Research, vol. 10, pp. 1633–1685, Dec. 2009.
- [7] C. Devin, A. Gupta, T. Darrell, P. Abbeel, and S. Levine, “Learning modular neural network policies for multi-task and multi-robot transfer,” in 2017 IEEE International Conference on Robotics and Automation (ICRA), May 2017, pp. 2169–2176.
- [8] A. Gupta, C. Devin, Y. Liu, P. Abbeel, and S. Levine, “Learning Invariant Feature Spaces to Transfer Skills with Reinforcement Learning,” Mar. 2017, arXiv:1703.02949 [cs]. [Online]. Available: http://arxiv.org/abs/1703.02949
- [9] M. K. Helwa and A. P. Schoellig, “Multi-robot transfer learning: A dynamical system perspective,” in 2017 IEEE/RSJ International Conference on Intelligent Robots and Systems (IROS), Sep. 2017, pp. 4702–4708, iSSN: 2153-0866.
- [10] T. Chen, A. Murali, and A. Gupta, “Hardware Conditioned Policies for Multi-Robot Transfer Learning,” in Advances in Neural Information Processing Systems, vol. 31. Curran Associates, Inc., 2018. [Online]. Available: https://proceedings.neurips.cc/paper/2018/hash/b8cfbf77a3d250a4523ba67a65a7d031-Abstract.html
- [11] K. Pereida, M. K. Helwa, and A. P. Schoellig, “Data-Efficient Multirobot, Multitask Transfer Learning for Trajectory Tracking,” IEEE Robotics and Automation Letters, vol. 3, no. 2, pp. 1260–1267, Apr. 2018, conference Name: IEEE Robotics and Automation Letters.
- [12] M. J. Sorocky, S. Zhou, and A. P. Schoellig, “Experience Selection Using Dynamics Similarity for Efficient Multi-Source Transfer Learning Between Robots,” Mar. 2020, arXiv:2003.13150 [cs, eess]. [Online]. Available: http://arxiv.org/abs/2003.13150
- [13] J. Bertrand, “Sur l’homogénéité dans les formules de physique”.” Cahiers de recherche de l’Academie de Sciences, vol. 86, pp. 916–920, 1878.
- [14] L. Rayleigh, “VIII. On the question of the stability of the flow of fluids,” The London, Edinburgh, and Dublin Philosophical Magazine and Journal of Science, vol. 34, no. 206, pp. 59–70, Jul. 1892, publisher: Taylor & Francis _eprint: https://doi.org/10.1080/14786449208620167. [Online]. Available: https://doi.org/10.1080/14786449208620167
- [15] J. Bakarji, J. Callaham, S. L. Brunton, and J. N. Kutz, “Dimensionally consistent learning with Buckingham Pi,” Nature Computational Science, vol. 2, no. 12, pp. 834–844, Dec. 2022. [Online]. Available: https://www.nature.com/articles/s43588-022-00355-5
- [16] K. Fukami and K. Taira, “Robust machine learning of turbulence through generalized Buckingham Pi-inspired pre-processing of training data,” p. A31.004, Jan. 2021, conference Name: APS Division of Fluid Dynamics Meeting Abstracts ADS Bibcode: 2021APS..DFDA31004F. [Online]. Available: https://ui.adsabs.harvard.edu/abs/2021APS..DFDA31004F
- [17] X. Xie, A. Samaei, J. Guo, W. K. Liu, and Z. Gan, “Data-driven discovery of dimensionless numbers and governing laws from scarce measurements,” Nature Communications, vol. 13, no. 1, p. 7562, Dec. 2022, number: 1 Publisher: Nature Publishing Group. [Online]. Available: https://www.nature.com/articles/s41467-022-35084-w
- [18] D. P. Bertsekas, Dynamic Programming and Optimal Control: Approximate Dynamic Programming. Nashua, NH: Athena scientific, 2012.
- [19] R. E. Kalman, “Contributions to the theory of optimal control,” Bol. soc. mat. mexicana, vol. 5, no. 2, pp. 102–119, 1960.
- [20] H. H. Asada and J.-J. E. Slotine, Robot Analysis and Control. New York: John Wiley & Sons, 1986.
- [21] B. Hanks and R. Skelton, “Closed-form solutions for linear regulator-design of mechanical systems including optimal weighting matrix selection,” National Aeronautics and Space Administration, NASA Technical Memorandum 104052, Jan. 1991, _eprint: https://arc.aiaa.org/doi/pdf/10.2514/6.1991-1117. [Online]. Available: https://arc.aiaa.org/doi/abs/10.2514/6.1991-1117

◄ Feelinglucky?